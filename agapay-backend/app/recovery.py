"""Offline authenticated-encrypted backups and EMPTY-target, quarantined restore.

No application, broker, SMTP or push provider is started. Keys come from a protected
environment variable, never command arguments or the archive. PostgreSQL uses an
external libpq service/credential file; no credential URL is echoed.
"""
import argparse
import base64
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
import time
from urllib.parse import quote
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from sqlalchemy import create_engine, inspect, select, update, delete
from sqlalchemy.orm import Session
from app.migrations import require_current
from app.schema_catalog import metadata
from app.recovery_models import DeliveryHold
from app.transfer_database import digest

MAGIC = b'AGAPAY-BACKUP-AES256-GCM-v1\n'
CHUNK = 1024 * 1024
MEMBERS = {'manifest.json', 'database.sqlite3', 'database.dump', 'rain.sqlite3'}


def file_hash(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(CHUNK), b''): result.update(chunk)
    return result.hexdigest()


def key_from_environment():
    try:
        key = base64.b64decode(os.environ.get('AGAPAY_BACKUP_KEY', ''), validate=True)
        if len(key) != 32: raise ValueError()
        return key
    except ValueError:
        raise RuntimeError('A protected base64-encoded 32-byte backup key is required') from None


def encrypt(source, target, key):
    nonce = os.urandom(12)
    cipher = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    cipher.authenticate_additional_data(MAGIC)
    with Path(source).open('rb') as reader, Path(target).open('xb') as writer:
        os.chmod(target, 0o600)
        writer.write(MAGIC + nonce)
        for chunk in iter(lambda: reader.read(CHUNK), b''): writer.write(cipher.update(chunk))
        writer.write(cipher.finalize()); writer.write(cipher.tag); writer.flush(); os.fsync(writer.fileno())


def decrypt(source, target, key):
    from cryptography.exceptions import InvalidTag
    with Path(source).open('rb') as reader:
        size = Path(source).stat().st_size
        if reader.read(len(MAGIC)) != MAGIC or size < len(MAGIC) + 28:
            raise RuntimeError('Unrecognized encrypted backup')
        nonce = reader.read(12); reader.seek(-16, 2); tag = reader.read(16); reader.seek(len(MAGIC) + 12)
        cipher = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
        cipher.authenticate_additional_data(MAGIC)
        remaining = size - len(MAGIC) - 28
        try:
            with Path(target).open('xb') as writer:
                os.chmod(target, 0o600)
                while remaining:
                    chunk = reader.read(min(CHUNK, remaining))
                    if not chunk: raise RuntimeError('Truncated encrypted backup')
                    remaining -= len(chunk); writer.write(cipher.update(chunk))
                writer.write(cipher.finalize())
        except InvalidTag:
            Path(target).unlink(missing_ok=True)
            raise RuntimeError('Backup authentication failed; no restore target written') from None


def sqlite_snapshot(source, target):
    source = Path(source).resolve()
    if not source.is_file(): raise RuntimeError('Required SQLite source is missing')
    with closing(sqlite3.connect('file:' + quote(source.as_posix()) + '?mode=ro', uri=True)) as reader, closing(sqlite3.connect(target)) as writer:
        reader.backup(writer)
        if writer.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('SQLite snapshot integrity failed')


def fingerprints(connection):
    return {table.name: digest(connection.execute(select(table).execution_options(stream_results=True)).mappings())
            for table in metadata.sorted_tables}


def pg_engine(service):
    if not service or not all(c.isalnum() or c in '_-' for c in service):
        raise RuntimeError('Use a reviewed libpq service name')
    return create_engine('postgresql+psycopg://', connect_args={'service': service})


def backup(destination, key, *, source=None, pg_service=None, rain=None, writers_stopped=False, pg_dump='pg_dump'):
    if not writers_stopped or bool(source) == bool(pg_service):
        raise RuntimeError('Stop all writers; choose exactly one explicit SQLite copy or PostgreSQL service')
    snapshot_started_at = datetime.now(timezone.utc).isoformat()
    destination = Path(destination).resolve()
    if destination.exists() or not destination.parent.is_dir():
        raise RuntimeError('Backup requires a new file in an existing protected directory')
    with tempfile.TemporaryDirectory(prefix='agapay-backup-',dir=os.environ.get('AGAPAY_RECOVERY_TEMP_DIRECTORY')) as temporary:
        stage = Path(temporary); os.chmod(stage, 0o700)
        if source:
            database = stage / 'database.sqlite3'; sqlite_snapshot(source, database)
            bind = create_engine('sqlite:///' + database.as_posix())
        else:
            database = stage / 'database.dump'; bind = pg_engine(pg_service)
        try:
            require_current(bind)
            with bind.begin() as connection:
                if pg_service:
                    names = ', '.join(connection.dialect.identifier_preparer.quote(t.name) for t in metadata.sorted_tables)
                    connection.exec_driver_sql('LOCK TABLE ' + names + ' IN SHARE MODE')
                before = fingerprints(connection)
                if pg_service:
                    subprocess.run([pg_dump, '--format=custom', '--no-owner', '--no-privileges',
                                    '--dbname=service=' + pg_service, '--file=' + str(database)],
                                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if rain: sqlite_snapshot(rain, stage / 'rain.sqlite3')
        finally: bind.dispose()
        manifest = dict(format='agapay-recovery-v1', created_at=datetime.now(timezone.utc).isoformat(),
            snapshot_started_at=snapshot_started_at, database_kind='postgresql' if pg_service else 'sqlite', tables=before,
            files={p.name: file_hash(p) for p in stage.iterdir()}, writer_quiescence='operator-confirmed',
            excludes='Environment secrets, identity/MFA encryption keys, backup keys and model binaries; retain protected key escrow and immutable artifact references separately')
        (stage / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True), encoding='utf-8')
        archive = stage / 'package.tar'
        with tarfile.open(archive, 'w') as bundle:
            for path in sorted(stage.iterdir()):
                if path != archive: bundle.add(path, arcname=path.name, recursive=False)
        encrypt(archive, destination, key)
    return dict(backup_sha256=file_hash(destination), encrypted_bytes=destination.stat().st_size,
                created_at=manifest['created_at'], tables={name: item[1] for name, item in before.items()})


def quarantine(bind, backup_hash):
    from app.models import AuthSession, NotificationDevice, utc_now
    from app.identity_models import IdentityMail, IdentityAction
    from app.privacy_models import RecoveryFence
    from app.services.privacy import evidence
    from app.services.delivery_recovery import declare
    with Session(bind) as db:
        db.execute(delete(AuthSession))
        db.execute(update(NotificationDevice).values(enabled=False, provider_token=None, token_hash=None,
            revision=NotificationDevice.revision+1))
        # R2 P0: delivery rows keep their restored state and evidence. A new RECOVERING
        # generation holds every operational and exercise delivery whose outcome may
        # have become unknowable; no delivery is claimable until an operator activates.
        generation = declare(db, kind='restore', source_backup_sha256=backup_hash,
                             reason='Restored from an encrypted backup; outcomes after the backup are unknowable')
        number = generation.generation
        held = db.execute(select(DeliveryHold.original_state).where(DeliveryHold.generation == number)).scalars().all()
        pending = sum(state in ('PENDING', 'FAILED') for state in held)
        processing = sum(state in ('PROCESSING', 'UNKNOWN') for state in held)
        db.execute(update(IdentityMail).where(IdentityMail.state == 'PENDING').values(state='SUPPRESSED', completed_at=utc_now()))
        db.execute(update(IdentityMail).where(IdentityMail.state == 'SENDING').values(state='UNKNOWN', completed_at=utc_now()))
        db.execute(update(IdentityAction).where(IdentityAction.used_at.is_(None)).values(used_at=utc_now(), secret_ciphertext=None))
        fence = db.get(RecoveryFence, 1)
        if fence: fence.state='QUARANTINED'; fence.backup_sha256=backup_hash
        else: db.add(RecoveryFence(id=1, state='QUARANTINED', backup_sha256=backup_hash))
        evidence(db, None, backup_hash, 'restore_quarantined', deliveries_held_unsent=pending,
                 deliveries_held_uncertain=processing, delivery_generation=number,
                 external_delivery='fenced until operator activation', privacy_withdrawals='reconcile before release')
        db.commit()
    return dict(deliveries_held_unsent=pending, deliveries_held_uncertain=processing, delivery_generation=number)


def restore(archive, destination, key, *, pg_service=None, pg_restore='pg_restore', max_bytes=20*1024**3):
    started = time.monotonic(); destination = Path(destination).resolve()
    if destination.exists(): raise RuntimeError('Restore destination must not exist; never overwrite a deployment')
    if not destination.parent.is_dir(): raise RuntimeError('Restore parent directory must already exist')
    with tempfile.TemporaryDirectory(prefix='agapay-restore-',dir=os.environ.get('AGAPAY_RECOVERY_TEMP_DIRECTORY')) as temporary:
        stage = Path(temporary); os.chmod(stage, 0o700)
        package = stage / 'package.tar'; decrypt(archive, package, key) # Authenticate BEFORE extraction/DB writes.
        with tarfile.open(package, 'r') as bundle:
            members = bundle.getmembers()
            if (len({m.name for m in members}) != len(members) or not members or
                any(m.name not in MEMBERS or not m.isfile() for m in members) or sum(m.size for m in members) > max_bytes):
                raise RuntimeError('Unsafe or oversized recovery package')
            for member in members:
                with bundle.extractfile(member) as reader, (stage / member.name).open('xb') as writer:
                    shutil.copyfileobj(reader, writer, CHUNK)
        value = json.loads((stage / 'manifest.json').read_text(encoding='utf-8'))
        if value['format'] != 'agapay-recovery-v1' or set(value['files']) != {m.name for m in members} - {'manifest.json'}:
            raise RuntimeError('Recovery manifest mismatch')
        if any(file_hash(stage/name) != digest_value for name, digest_value in value['files'].items()):
            raise RuntimeError('Recovery member checksum mismatch')
        if value['database_kind'] == 'postgresql':
            bind = pg_engine(pg_service)
            if inspect(bind).get_table_names():
                bind.dispose(); raise RuntimeError('PostgreSQL restore target must be completely empty')
        elif value['database_kind'] == 'sqlite' and not pg_service:
            bind = None
        else: raise RuntimeError('Choose a restore target matching the backup database kind')
        destination.mkdir(mode=0o700)
        try:
            if bind is not None:
                subprocess.run([pg_restore, '--single-transaction', '--exit-on-error', '--no-owner', '--no-privileges',
                    '--dbname=service='+pg_service, str(stage/'database.dump')], check=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                shutil.copyfile(stage/'database.sqlite3', destination/'database.sqlite3')
                bind = create_engine('sqlite:///' + (destination/'database.sqlite3').as_posix())
            require_current(bind)
            with bind.connect() as connection:
                actual = {name: list(item) for name,item in fingerprints(connection).items()}
            if actual != value['tables']: raise RuntimeError('Restored rows differ from encrypted source fingerprint')
            controls = quarantine(bind, file_hash(archive))
            if (stage/'rain.sqlite3').exists():
                sqlite_snapshot(stage/'rain.sqlite3', destination/'rain.sqlite3')
            report = dict(status='verified_and_quarantined', backup_sha256=file_hash(archive),
                package_capture_started_at=value.get('snapshot_started_at',value['created_at']), source_data_cutoff_at=None, actual_data_loss_seconds=None, completed_at=datetime.now(timezone.utc).isoformat(),
                restore_seconds=round(time.monotonic()-started, 3),
                package_age_seconds=max(0, (datetime.now(timezone.utc)-datetime.fromisoformat(value.get('snapshot_started_at',value['created_at']))).total_seconds()),
                tables={name: item[1] for name,item in value['tables'].items()}, **controls,
                activation='blocked pending current privacy withdrawals, provider reconciliation and approved operator review')
            (destination/'restore-report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
            return report
        except Exception:
            if bind is not None:
                try:
                    if inspect(bind).has_table('recovery_fences'): quarantine(bind, file_hash(archive))
                except Exception: pass # Schema failure itself blocks serving; never clear a recovery fence.
            raise
        finally:
            if bind is not None: bind.dispose()


def main():
    parser=argparse.ArgumentParser(description=__doc__); commands=parser.add_subparsers(dest='command',required=True)
    create=commands.add_parser('backup'); create.add_argument('--source-copy',type=Path);create.add_argument('--pg-service')
    create.add_argument('--rain-copy',type=Path);create.add_argument('--writers-stopped',action='store_true');create.add_argument('--output',required=True,type=Path)
    recover=commands.add_parser('restore');recover.add_argument('--backup',required=True,type=Path);recover.add_argument('--new-directory',required=True,type=Path);recover.add_argument('--pg-service')
    args=parser.parse_args()
    try:
        key=key_from_environment()
        result=backup(args.output,key,source=args.source_copy,pg_service=args.pg_service,rain=args.rain_copy,writers_stopped=args.writers_stopped) if args.command=='backup' else restore(args.backup,args.new_directory,key,pg_service=args.pg_service)
        print(json.dumps(result,indent=2))
    except Exception:
        raise SystemExit('Recovery operation failed. Inspect the protected inputs/target privately; no connection secrets or personal rows are printed. Failed targets stay quarantined and must not be served.') from None


if __name__=='__main__':main()

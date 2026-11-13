"""Run one bounded drill-only deadline review; sends no external messages."""
import argparse
from app.database import SessionLocal
from app.services.sos_response import process_due

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, default=50)
    print(process_due(SessionLocal, limit=parser.parse_args().limit))

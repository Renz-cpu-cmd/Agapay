import {spawn} from 'node:child_process';
import {productionConfig} from './production-config.mjs';
try{productionConfig(process.env);}catch{console.error('Production configuration incomplete. Review HTTPS origins and environment; secret values are not printed.');process.exit(1);}
const child=spawn(process.execPath,['node_modules/next/dist/bin/next','start','--hostname','127.0.0.1','--port',process.env.PORT||'3000'],{stdio:'inherit',env:{...process.env,NODE_ENV:'production'}});
child.on('exit',code=>process.exit(code??1));

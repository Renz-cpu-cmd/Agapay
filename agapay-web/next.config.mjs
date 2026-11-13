import {productionConfig} from './scripts/production-config.mjs';
if(process.env.AGAPAY_ENVIRONMENT==='production')productionConfig(process.env);
/** @type {import('next').NextConfig} */
const nextConfig = {
  devIndicators: false,
  async headers(){return [{source:'/:path*',headers:[
    {key:'X-Content-Type-Options',value:'nosniff'},
    {key:'X-Frame-Options',value:'DENY'},
    ...(process.env.NODE_ENV==='production'?[{key:'Strict-Transport-Security',value:'max-age=15552000'}]:[]),
    {key:'Referrer-Policy',value:'strict-origin-when-cross-origin'},
    {key:'Permissions-Policy',value:'camera=(), microphone=(), geolocation=(self)'},
  ]}];},
};
export default nextConfig;

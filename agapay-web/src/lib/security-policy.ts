export function securityPolicy(nonce:string,development=false,maps=false){
  if(!/^[A-Za-z0-9+/=]{24,}$/.test(nonce))throw Error("Invalid request nonce");
  return ["default-src 'self'",`script-src 'self' 'nonce-${nonce}' 'strict-dynamic' https://maps.googleapis.com https://maps.gstatic.com${development||maps?" 'unsafe-eval'":""}${maps?" blob:":""}`,
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com", "img-src 'self' data: blob: https://*.googleapis.com https://*.gstatic.com https://*.google.com https://*.googleusercontent.com https://*.ggpht.com",
    "connect-src 'self' https://*.googleapis.com https://*.gstatic.com"+(maps?" https://*.google.com data: blob:":"")+(development?" ws://localhost:* ws://127.0.0.1:*":""),
    "font-src 'self' data: https://fonts.gstatic.com", "frame-src https://www.google.com https://maps.google.com", "worker-src 'self' blob:",
    "object-src 'none'", "base-uri 'self'", "form-action 'self'", "frame-ancestors 'none'"].join('; ');
}

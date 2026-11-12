import {NextRequest,NextResponse} from "next/server";
import {randomBytes} from "node:crypto";

import {securityPolicy} from "@/lib/security-policy";

export function proxy(request:NextRequest){
  const nonce=randomBytes(24).toString('base64');
  const csp=securityPolicy(nonce,process.env.NODE_ENV==='development',Boolean(process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY));
  const headers=new Headers(request.headers);headers.set('x-nonce',nonce);headers.set('Content-Security-Policy',csp);
  const response=NextResponse.next({request:{headers}});
  response.headers.set('Content-Security-Policy',csp);
  response.headers.set('Cache-Control','private, no-store');
  return response;
}
export const config={matcher:['/((?!api|_next/static|_next/image|favicon.ico).*)']};

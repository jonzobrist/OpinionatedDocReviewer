import { NextRequest, NextResponse } from 'next/server';
import { summarizeForwardedHeaders } from './src/lib/requestLog';

export function middleware(request: NextRequest) {
  const { xForwardedFor, xRealIp } = summarizeForwardedHeaders(request.headers);
  const host = request.headers.get('host') ?? '-';
  console.info(
    `[frontend] ${request.method} ${request.nextUrl.pathname} xff="${xForwardedFor}" xri="${xRealIp}" host="${host}"`
  );
  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)']
};

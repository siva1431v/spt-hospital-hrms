import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function proxy(request: NextRequest) {
  const token = request.cookies.get('token')?.value;
  const { pathname } = request.nextUrl;

  const isAuthPage = pathname.startsWith('/login');

  // Handle root URL redirect cleanly
  if (pathname === '/') {
    if (token) {
      return NextResponse.redirect(new URL('/dashboard', request.url));
    } else {
      return NextResponse.redirect(new URL('/login', request.url));
    }
  }

  // Redirect unauthenticated requests for protected routes to /login
  if (!token && !isAuthPage) {
    return NextResponse.redirect(new URL('/login', request.url));
  }

  // Redirect authenticated requests away from /login to /dashboard
  if (token && isAuthPage) {
    return NextResponse.redirect(new URL('/dashboard', request.url));
  }

  return NextResponse.next();
}

export const middleware = proxy;

export const config = {
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico).*)'],
};

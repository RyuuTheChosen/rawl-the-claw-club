import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Pre-launch middleware: redirect everything to /early-access in production.
 * Skipped entirely in local dev so all routes remain accessible.
 * Remove this file once the platform is live.
 */
export function middleware(request: NextRequest) {
  // Skip in development — all routes stay accessible
  if (process.env.NODE_ENV === "development") {
    return NextResponse.next();
  }

  const { pathname } = request.nextUrl;

  // Allow early-access page, static assets, and Next.js internals
  if (
    pathname === "/early-access" ||
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api") ||
    pathname === "/favicon.ico" ||
    pathname === "/robots.txt" ||
    pathname === "/sitemap.xml"
  ) {
    return NextResponse.next();
  }

  const url = request.nextUrl.clone();
  url.pathname = "/early-access";
  return NextResponse.redirect(url);
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico).*)",
  ],
};

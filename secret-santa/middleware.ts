import { NextResponse, type NextRequest } from 'next/server'
import { getIronSession, SessionOptions } from 'iron-session'
import { cookies } from 'next/headers'

interface SessionData {
  userId?: string
  isLoggedIn: boolean
}

const sessionOptions: SessionOptions = {
  password: process.env.SESSION_SECRET || 'complex_password_at_least_32_characters_long',
  cookieName: 'secret-santa-session',
  cookieOptions: {
    secure: process.env.NODE_ENV === 'production',
    httpOnly: true,
    sameSite: 'lax' as const,
    maxAge: 60 * 60 * 24 * 7, // 1 week
  },
}

export async function middleware(request: NextRequest) {
  const cookieStore = await cookies()
  const session = await getIronSession<SessionData>(cookieStore, sessionOptions)

  const isLoggedIn = session.isLoggedIn && session.userId

  // Public routes that don't require authentication
  const publicPaths = ['/login', '/api/auth/login', '/api/auth/logout']
  const isPublicPath = publicPaths.some((path) => request.nextUrl.pathname.startsWith(path))

  // Redirect to login if user is not authenticated and trying to access protected routes
  if (!isLoggedIn && !isPublicPath) {
    const url = request.nextUrl.clone()
    url.pathname = '/login'
    return NextResponse.redirect(url)
  }

  // Redirect to dashboard if user is authenticated and trying to access login
  if (isLoggedIn && request.nextUrl.pathname === '/login') {
    const url = request.nextUrl.clone()
    url.pathname = '/dashboard'
    return NextResponse.redirect(url)
  }

  return NextResponse.next()
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
}

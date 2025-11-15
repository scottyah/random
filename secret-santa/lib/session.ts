import { getIronSession, SessionOptions } from 'iron-session'
import { cookies } from 'next/headers'

export interface SessionData {
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

export async function getSession() {
  const cookieStore = await cookies()
  const session = await getIronSession<SessionData>(cookieStore, sessionOptions)

  if (!session.isLoggedIn) {
    session.isLoggedIn = false
  }

  return session
}

export async function login(userId: string) {
  const session = await getSession()
  session.userId = userId
  session.isLoggedIn = true
  await session.save()
}

export async function logout() {
  const session = await getSession()
  session.destroy()
}

export async function getCurrentUser() {
  const session = await getSession()
  if (!session.isLoggedIn || !session.userId) {
    return null
  }
  return session.userId
}

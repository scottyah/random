import { NextResponse } from 'next/server'
import { cookies } from 'next/headers'
import { getUserById, getGiverForUser } from '@/lib/db/queries'
import { sendWishlistReadyEmail } from '@/lib/email'

export async function POST() {
  try {
    const cookieStore = await cookies()
    const userId = cookieStore.get('user_id')?.value

    if (!userId) {
      return NextResponse.json({ error: 'Not authenticated' }, { status: 401 })
    }

    const user = getUserById(userId)
    if (!user) {
      return NextResponse.json({ error: 'User not found' }, { status: 404 })
    }

    const year = new Date().getFullYear()
    const giverAssignment = getGiverForUser(userId, year)

    if (!giverAssignment) {
      return NextResponse.json(
        { error: 'No gifter found for this year' },
        { status: 404 }
      )
    }

    const success = await sendWishlistReadyEmail(
      giverAssignment.giver.email,
      giverAssignment.giver.full_name,
      user.full_name
    )

    if (success) {
      return NextResponse.json({
        success: true,
        message: 'Your Secret Santa has been notified that your wishlist is ready!',
      })
    } else {
      return NextResponse.json(
        { error: 'Failed to send notification' },
        { status: 500 }
      )
    }
  } catch (error) {
    console.error('Error notifying gifter:', error)
    return NextResponse.json(
      { error: 'Internal server error', details: String(error) },
      { status: 500 }
    )
  }
}

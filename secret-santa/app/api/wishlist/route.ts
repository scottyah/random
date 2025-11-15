import { NextResponse } from 'next/server'
import { getCurrentUser } from '@/lib/session'
import { createWishlistItem, getWishlistForUser } from '@/lib/db/queries'

export async function GET() {
  try {
    const userId = await getCurrentUser()
    if (!userId) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const wishlist = getWishlistForUser(userId)
    return NextResponse.json({ wishlist })
  } catch (error) {
    console.error('Error fetching wishlist:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}

export async function POST(request: Request) {
  try {
    const userId = await getCurrentUser()
    if (!userId) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const { title, description, price, url } = await request.json()

    if (!title) {
      return NextResponse.json(
        { error: 'Title is required' },
        { status: 400 }
      )
    }

    const item = createWishlistItem(userId, title, description || null, price || null, url || null)
    return NextResponse.json({ item })
  } catch (error) {
    console.error('Error creating wishlist item:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}

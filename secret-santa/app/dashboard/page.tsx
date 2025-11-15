import { redirect } from 'next/navigation'
import { getCurrentUser } from '@/lib/session'
import { getUserById, getAssignmentForUser, getWishlistForUser } from '@/lib/db/queries'
import { AssignmentWithReceiver, WishlistItem, Profile } from '@/lib/types'
import DashboardClient from './DashboardClient'

async function getDaysRemaining(): Promise<number> {
  const eventDate = new Date(process.env.NEXT_PUBLIC_SECRET_SANTA_DATE || '2025-12-25')
  const today = new Date()
  const diffTime = eventDate.getTime() - today.getTime()
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))
  return diffDays
}

export default async function DashboardPage() {
  const userId = await getCurrentUser()

  if (!userId) {
    redirect('/login')
  }

  // Get user's profile
  const profile = getUserById(userId)

  if (!profile) {
    return <div>Profile not found</div>
  }

  // Get current year
  const year = new Date().getFullYear()

  // Get user's assignment (who they are giving to)
  const assignment = getAssignmentForUser(userId, year)

  // Get target's wishlist if assignment exists
  let targetWishlist: WishlistItem[] = []
  if (assignment) {
    targetWishlist = getWishlistForUser(assignment.receiver.id)
  }

  // Get user's own wishlist
  const myWishlist = getWishlistForUser(userId)

  const daysRemaining = await getDaysRemaining()

  return (
    <DashboardClient
      profile={profile as Profile}
      assignment={assignment as AssignmentWithReceiver | null}
      targetWishlist={targetWishlist}
      myWishlist={myWishlist}
      daysRemaining={daysRemaining}
    />
  )
}

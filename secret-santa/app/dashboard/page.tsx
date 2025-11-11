import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
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
  const supabase = await createClient()

  // Get current user
  const {
    data: { user },
  } = await supabase.auth.getUser()

  if (!user) {
    redirect('/login')
  }

  // Get user's profile
  const { data: profile } = await supabase
    .from('profiles')
    .select('*')
    .eq('id', user.id)
    .single()

  if (!profile) {
    return <div>Profile not found</div>
  }

  // Get current year
  const year = new Date().getFullYear()

  // Get user's assignment (who they are giving to)
  const { data: assignment } = await supabase
    .from('assignments')
    .select(`
      *,
      receiver:profiles!assignments_receiver_id_fkey(*)
    `)
    .eq('giver_id', user.id)
    .eq('year', year)
    .single()

  // Get target's wishlist if assignment exists
  let targetWishlist: WishlistItem[] = []
  if (assignment) {
    const { data: wishlist } = await supabase
      .from('wishlist_items')
      .select('*')
      .eq('user_id', (assignment.receiver as any).id)
      .order('created_at', { ascending: false })

    targetWishlist = wishlist || []
  }

  // Get user's own wishlist
  const { data: myWishlist } = await supabase
    .from('wishlist_items')
    .select('*')
    .eq('user_id', user.id)
    .order('created_at', { ascending: false })

  const daysRemaining = await getDaysRemaining()

  return (
    <DashboardClient
      profile={profile as Profile}
      assignment={assignment as AssignmentWithReceiver | null}
      targetWishlist={targetWishlist}
      myWishlist={myWishlist || []}
      daysRemaining={daysRemaining}
    />
  )
}

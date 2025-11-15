'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { AssignmentWithReceiver, WishlistItem, Profile } from '@/lib/types'
import WishlistEditor from '@/components/WishlistEditor'
import TargetWishlist from '@/components/TargetWishlist'

interface DashboardClientProps {
  profile: Profile
  assignment: AssignmentWithReceiver | null
  targetWishlist: WishlistItem[]
  myWishlist: WishlistItem[]
  daysRemaining: number
}

export default function DashboardClient({
  profile,
  assignment,
  targetWishlist: initialTargetWishlist,
  myWishlist: initialMyWishlist,
  daysRemaining,
}: DashboardClientProps) {
  const router = useRouter()
  const [targetWishlist, setTargetWishlist] = useState(initialTargetWishlist)
  const [myWishlist, setMyWishlist] = useState(initialMyWishlist)
  const [activeTab, setActiveTab] = useState<'target' | 'my-wishlist'>('target')

  const handleSignOut = async () => {
    await fetch('/api/auth/logout', { method: 'POST' })
    router.push('/login')
    router.refresh()
  }

  const handleRefresh = () => {
    router.refresh()
  }

  return (
    <div className="min-h-screen relative">
      {/* Background gradient layer */}
      <div className="fixed inset-0 bg-gradient-to-br from-red-300 via-gray-200 to-green-300" style={{ zIndex: 0 }} />

      {/* Content layer */}
      <div className="relative" style={{ zIndex: 10 }}>
      {/* Header */}
      <header className="bg-gray-100/90 backdrop-blur-sm shadow-sm border-b border-gray-300">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-2xl font-bold text-red-600">🎅 Secret Santa</h1>
              <p className="text-sm text-gray-600">Welcome, {profile.full_name}!</p>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right">
                <p className="text-sm font-medium text-gray-900">
                  {daysRemaining > 0 ? (
                    <>
                      <span className="text-2xl font-bold text-red-600">{daysRemaining}</span>
                      <span className="text-gray-600 ml-1">
                        day{daysRemaining !== 1 ? 's' : ''} remaining
                      </span>
                    </>
                  ) : daysRemaining === 0 ? (
                    <span className="text-2xl font-bold text-green-600">Today is the day! 🎉</span>
                  ) : (
                    <span className="text-gray-600">Event has passed</span>
                  )}
                </p>
              </div>
              <button
                onClick={handleSignOut}
                className="px-4 py-2 text-sm text-gray-700 hover:text-gray-900 border border-gray-300 rounded-lg hover:bg-gray-200 transition"
              >
                Sign Out
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Assignment Info */}
        {assignment ? (
          <div className="bg-white/95 backdrop-blur-sm rounded-xl shadow-lg p-6 mb-8 border-2 border-red-400">
            <h2 className="text-xl font-bold text-red-600 mb-3">
              Your Secret Santa Assignment
            </h2>
            <p className="text-gray-700 mb-3">
              You are the Secret Santa for:
            </p>
            <div className="bg-gray-50 rounded-lg p-6 text-center border border-gray-300">
              <p className="text-3xl font-bold text-red-700">
                🎅 {(assignment.receiver as any).full_name}
              </p>
              <p className="text-sm text-green-700 font-medium mt-2">
                Check out their wishlist below!
              </p>
            </div>
          </div>
        ) : (
          <div className="bg-yellow-100/90 border border-yellow-300 rounded-lg p-6 mb-8">
            <p className="text-yellow-800">
              You don't have an assignment yet. Please wait for the organizer to assign Secret Santas.
            </p>
          </div>
        )}

        {/* Tabs */}
        <div className="mb-6">
          <div className="border-b border-gray-300">
            <nav className="-mb-px flex space-x-8">
              <button
                onClick={() => setActiveTab('target')}
                className={`${
                  activeTab === 'target'
                    ? 'border-red-500 text-red-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-400'
                } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm transition`}
              >
                {assignment ? `${(assignment.receiver as any).full_name}'s Wishlist` : 'Their Wishlist'}
              </button>
              <button
                onClick={() => setActiveTab('my-wishlist')}
                className={`${
                  activeTab === 'my-wishlist'
                    ? 'border-red-500 text-red-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-400'
                } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm transition`}
              >
                My Wishlist
              </button>
            </nav>
          </div>
        </div>

        {/* Tab Content */}
        {activeTab === 'target' && assignment && (
          <TargetWishlist
            wishlist={targetWishlist}
            targetName={(assignment.receiver as any).full_name}
            onRefresh={handleRefresh}
          />
        )}

        {activeTab === 'my-wishlist' && (
          <WishlistEditor
            wishlist={myWishlist}
            userId={profile.id}
            onRefresh={handleRefresh}
          />
        )}
      </main>
      </div>
    </div>
  )
}

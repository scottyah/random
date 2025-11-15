'use client'

import { useState } from 'react'
import { WishlistItem } from '@/lib/types'

interface TargetWishlistProps {
  wishlist: WishlistItem[]
  targetName: string
  onRefresh: () => void
}

export default function TargetWishlist({
  wishlist,
  targetName,
  onRefresh,
}: TargetWishlistProps) {
  const [loading, setLoading] = useState<string | null>(null)

  const handleTogglePurchased = async (item: WishlistItem) => {
    setLoading(item.id)

    try {
      const response = await fetch(`/api/wishlist/${item.id}/purchase`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          is_purchased: !item.is_purchased,
        }),
      })

      if (!response.ok) throw new Error('Failed to update item')

      onRefresh()
    } catch (error) {
      console.error('Error toggling purchased status:', error)
      alert('Failed to update item')
    } finally {
      setLoading(null)
    }
  }

  const purchasedCount = wishlist.filter((item) => item.is_purchased).length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gray-100/90 backdrop-blur-sm rounded-lg shadow-md p-6 border border-gray-300">
        <h2 className="text-2xl font-semibold text-gray-900 mb-4">
          {targetName}'s Wishlist
        </h2>

        {wishlist.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-center">
            <div className="bg-blue-100 rounded-lg p-4">
              <p className="text-sm text-gray-600 mb-1">Total Items</p>
              <p className="text-2xl font-bold text-blue-600">{wishlist.length}</p>
            </div>
            <div className="bg-green-100 rounded-lg p-4">
              <p className="text-sm text-gray-600 mb-1">Items Purchased</p>
              <p className="text-2xl font-bold text-green-600">
                {purchasedCount} / {wishlist.length}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Wishlist Items */}
      {wishlist.length === 0 ? (
        <div className="bg-gray-100/90 backdrop-blur-sm rounded-lg shadow-md p-8 text-center border border-gray-300">
          <p className="text-gray-500">
            {targetName} hasn't added any items to their wishlist yet.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {wishlist.map((item) => (
            <div
              key={item.id}
              className={`bg-gray-100/90 backdrop-blur-sm rounded-lg shadow-sm p-4 hover:shadow-md transition border ${
                item.is_purchased ? 'border-green-500 border-2' : 'border-gray-300'
              }`}
            >
              <div className="flex justify-between items-start gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3
                      className={`font-semibold ${
                        item.is_purchased
                          ? 'text-green-400 line-through'
                          : 'text-green-900'
                      }`}
                    >
                      {item.title}
                    </h3>
                    {item.is_purchased && (
                      <span className="px-2 py-0.5 text-xs font-medium bg-green-100 text-green-800 rounded">
                        ✓ Purchased
                      </span>
                    )}
                  </div>
                  {item.description && (
                    <p
                      className={`text-sm mt-1 ${
                        item.is_purchased ? 'text-green-400' : 'text-green-700'
                      }`}
                    >
                      {item.description}
                    </p>
                  )}
                  {item.url && (
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={`text-sm mt-1 inline-block ${
                        item.is_purchased
                          ? 'text-green-400 hover:text-green-500'
                          : 'text-blue-600 hover:underline'
                      }`}
                    >
                      View Product →
                    </a>
                  )}
                </div>
                <button
                  onClick={() => handleTogglePurchased(item)}
                  disabled={loading === item.id}
                  className={`px-3 py-1 text-sm rounded font-medium transition disabled:opacity-50 shrink-0 ${
                    item.is_purchased
                      ? 'bg-gray-300 hover:bg-gray-400 text-gray-700'
                      : 'bg-green-600 hover:bg-green-700 text-white'
                  }`}
                >
                  {loading === item.id
                    ? '...'
                    : item.is_purchased
                    ? 'Undo'
                    : 'Purchased'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {wishlist.length > 0 && (
        <div className="bg-blue-100/90 border border-blue-200 rounded-lg p-4">
          <p className="text-sm text-blue-800">
            💡 <strong>Tip:</strong> Mark items as purchased so you remember what you've already bought!
            {targetName} won't see which items you've marked as purchased.
          </p>
        </div>
      )}
    </div>
  )
}

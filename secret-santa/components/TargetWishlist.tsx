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

  const totalPrice = wishlist.reduce((sum, item) => {
    return sum + (item.price || 0)
  }, 0)

  const purchasedCount = wishlist.filter((item) => item.is_purchased).length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <h2 className="text-2xl font-semibold text-gray-900 mb-4">
          {targetName}'s Wishlist
        </h2>

        {wishlist.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-center">
            <div className="bg-blue-50 rounded-lg p-4">
              <p className="text-sm text-gray-600 mb-1">Total Items</p>
              <p className="text-2xl font-bold text-blue-600">{wishlist.length}</p>
            </div>
            <div className="bg-green-50 rounded-lg p-4">
              <p className="text-sm text-gray-600 mb-1">Items Purchased</p>
              <p className="text-2xl font-bold text-green-600">
                {purchasedCount} / {wishlist.length}
              </p>
            </div>
            <div className="bg-purple-50 rounded-lg p-4">
              <p className="text-sm text-gray-600 mb-1">Estimated Total</p>
              <p className="text-2xl font-bold text-purple-600">
                ${totalPrice.toFixed(2)}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Wishlist Items */}
      {wishlist.length === 0 ? (
        <div className="bg-white rounded-lg shadow-md p-8 text-center">
          <p className="text-gray-500">
            {targetName} hasn't added any items to their wishlist yet.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {wishlist.map((item) => (
            <div
              key={item.id}
              className={`bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition ${
                item.is_purchased ? 'border-2 border-green-500' : ''
              }`}
            >
              <div className="flex justify-between items-start mb-3">
                <div className="flex-1">
                  <h3
                    className={`text-lg font-semibold ${
                      item.is_purchased
                        ? 'text-gray-400 line-through'
                        : 'text-gray-900'
                    }`}
                  >
                    {item.title}
                  </h3>
                  {item.is_purchased && (
                    <span className="inline-block mt-1 px-2 py-1 text-xs font-medium bg-green-100 text-green-800 rounded">
                      ✓ Purchased
                    </span>
                  )}
                </div>
                {item.price && (
                  <span
                    className={`text-lg font-bold ml-3 ${
                      item.is_purchased ? 'text-gray-400' : 'text-green-600'
                    }`}
                  >
                    ${item.price.toFixed(2)}
                  </span>
                )}
              </div>

              {item.description && (
                <p
                  className={`text-sm mb-3 ${
                    item.is_purchased ? 'text-gray-400' : 'text-gray-600'
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
                  className={`text-sm block mb-3 ${
                    item.is_purchased
                      ? 'text-gray-400 hover:text-gray-500'
                      : 'text-blue-600 hover:underline'
                  }`}
                >
                  View Product →
                </a>
              )}

              <button
                onClick={() => handleTogglePurchased(item)}
                disabled={loading === item.id}
                className={`w-full px-4 py-2 rounded-lg font-medium transition disabled:opacity-50 ${
                  item.is_purchased
                    ? 'bg-gray-200 hover:bg-gray-300 text-gray-700'
                    : 'bg-green-600 hover:bg-green-700 text-white'
                }`}
              >
                {loading === item.id
                  ? 'Updating...'
                  : item.is_purchased
                  ? 'Mark as Not Purchased'
                  : 'Mark as Purchased'}
              </button>
            </div>
          ))}
        </div>
      )}

      {wishlist.length > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <p className="text-sm text-blue-800">
            💡 <strong>Tip:</strong> Mark items as purchased so you remember what you've already bought!
            {targetName} won't see which items you've marked as purchased.
          </p>
        </div>
      )}
    </div>
  )
}

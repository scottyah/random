'use client'

import { useState, useEffect } from 'react'
import { WishlistItem } from '@/lib/types'

interface WishlistEditorProps {
  wishlist: WishlistItem[]
  userId: string
  onRefresh: () => void
}

export default function WishlistEditor({
  wishlist: initialWishlist,
  userId,
  onRefresh,
}: WishlistEditorProps) {
  const [wishlist, setWishlist] = useState(initialWishlist)
  const [isAdding, setIsAdding] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    url: '',
  })
  const [loading, setLoading] = useState(false)
  const [notifyLoading, setNotifyLoading] = useState(false)
  const [notifySuccess, setNotifySuccess] = useState(false)

  // Sync with props when they change
  useEffect(() => {
    setWishlist(initialWishlist)
  }, [initialWishlist])

  const resetForm = () => {
    setFormData({ title: '', description: '', url: '' })
    setIsAdding(false)
    setEditingId(null)
  }

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)

    // Create optimistic item with temporary ID
    const tempId = `temp-${Date.now()}`
    const optimisticItem: WishlistItem = {
      id: tempId,
      user_id: userId,
      title: formData.title,
      description: formData.description || null,
      price: null,
      url: formData.url || null,
      is_purchased: false,
      purchased_by: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }

    // Optimistically add to UI
    setWishlist([optimisticItem, ...wishlist])
    resetForm()

    try {
      const response = await fetch('/api/wishlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: optimisticItem.title,
          description: optimisticItem.description,
          price: null,
          url: optimisticItem.url,
        }),
      })

      if (!response.ok) {
        // Revert on error
        setWishlist(wishlist.filter(item => item.id !== tempId))
        throw new Error('Failed to add item')
      }

      onRefresh()
    } catch (error) {
      console.error('Error adding item:', error)
      alert('Failed to add item')
    } finally {
      setLoading(false)
    }
  }

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingId) return

    setLoading(true)

    try {
      const response = await fetch(`/api/wishlist/${editingId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: formData.title,
          description: formData.description || null,
          price: null,
          url: formData.url || null,
        }),
      })

      if (!response.ok) throw new Error('Failed to update item')

      resetForm()
      onRefresh()
    } catch (error) {
      console.error('Error updating item:', error)
      alert('Failed to update item')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this item?')) return

    // Optimistically remove item from UI
    const previousWishlist = wishlist
    setWishlist(wishlist.filter(item => item.id !== id))

    try {
      const response = await fetch(`/api/wishlist/${id}`, {
        method: 'DELETE',
      })

      if (!response.ok) {
        // Revert on error
        setWishlist(previousWishlist)
        throw new Error('Failed to delete item')
      }

      onRefresh()
    } catch (error) {
      console.error('Error deleting item:', error)
      alert('Failed to delete item')
    }
  }

  const startEdit = (item: WishlistItem) => {
    setEditingId(item.id)
    setFormData({
      title: item.title,
      description: item.description || '',
      url: item.url || '',
    })
    setIsAdding(false)
  }

  const handleNotifyGifter = async () => {
    setNotifyLoading(true)
    try {
      const response = await fetch('/api/wishlist/notify-gifter', {
        method: 'POST',
      })

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.error || 'Failed to notify gifter')
      }

      setNotifySuccess(true)
      setTimeout(() => setNotifySuccess(false), 5000)
    } catch (error) {
      console.error('Error notifying gifter:', error)
      alert('Failed to notify your Secret Santa. Please try again.')
    } finally {
      setNotifyLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-semibold text-gray-900">My Wishlist</h2>
        <div className="flex gap-2">
          {!isAdding && !editingId && wishlist.length > 0 && (
            <button
              onClick={handleNotifyGifter}
              disabled={notifyLoading || notifySuccess}
              className={`px-4 py-2 rounded-lg transition disabled:opacity-50 ${
                notifySuccess
                  ? 'bg-green-100 text-green-700'
                  : 'bg-blue-600 hover:bg-blue-700 text-white'
              }`}
            >
              {notifyLoading
                ? 'Sending...'
                : notifySuccess
                ? '✓ Notified!'
                : '✉️ Notify My Santa'}
            </button>
          )}
          {!isAdding && !editingId && (
            <button
              onClick={() => setIsAdding(true)}
              className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg transition"
            >
              + Add Item
            </button>
          )}
        </div>
      </div>

      {/* Add/Edit Form */}
      {(isAdding || editingId) && (
        <div className="bg-gray-100/90 backdrop-blur-sm rounded-lg shadow-md p-6 border border-gray-300">
          <h3 className="text-lg font-semibold mb-4 text-gray-900">
            {editingId ? 'Edit Item' : 'Add New Item'}
          </h3>
          <form onSubmit={editingId ? handleUpdate : handleAdd} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Title *
              </label>
              <input
                type="text"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                placeholder="e.g., Red sweater"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Description
              </label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                placeholder="Any specific details..."
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                URL (optional)
              </label>
              <input
                type="url"
                value={formData.url}
                onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                placeholder="https://example.com/product"
              />
            </div>

            <div className="flex gap-2">
              <button
                type="submit"
                disabled={loading}
                className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg transition disabled:opacity-50"
              >
                {loading ? 'Saving...' : editingId ? 'Update' : 'Add'}
              </button>
              <button
                type="button"
                onClick={resetForm}
                className="px-4 py-2 bg-gray-300 hover:bg-gray-400 text-gray-700 rounded-lg transition"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Wishlist Items */}
      {wishlist.length === 0 ? (
        <div className="bg-gray-100/90 backdrop-blur-sm rounded-lg shadow-md p-8 text-center border border-gray-300">
          <p className="text-gray-500">
            Your wishlist is empty. Add some items to help your Secret Santa!
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {wishlist.map((item) => (
            <div
              key={item.id}
              className="bg-gray-100/90 backdrop-blur-sm rounded-lg shadow-sm p-4 hover:shadow-md transition border border-gray-300"
            >
              <div className="flex justify-between items-start gap-4">
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-green-900">{item.title}</h3>
                  {item.description && (
                    <p className="text-green-700 text-sm mt-1">{item.description}</p>
                  )}
                  {item.url && (
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-blue-600 hover:underline mt-1 inline-block"
                    >
                      View Product →
                    </a>
                  )}
                </div>
                <div className="flex gap-2 shrink-0">
                  <button
                    onClick={() => startEdit(item)}
                    className="px-2 py-1 text-xs bg-blue-100 hover:bg-blue-200 text-blue-700 rounded transition"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleDelete(item.id)}
                    className="px-2 py-1 text-xs bg-red-100 hover:bg-red-200 text-red-700 rounded transition"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

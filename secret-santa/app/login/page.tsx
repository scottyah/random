'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import ChristmasBackground from '@/components/ChristmasBackground'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const router = useRouter()

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      })

      const data = await response.json()

      if (!response.ok) {
        setError(data.error || 'Login failed')
        return
      }

      if (data.success) {
        router.push('/dashboard')
        router.refresh()
      }
    } catch (err) {
      setError('An unexpected error occurred')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden">
      {/* Festive gradient background */}
      <div className="absolute inset-0 bg-gradient-to-br from-red-900 via-green-800 to-red-900" />

      {/* Christmas background with snowflakes */}
      <ChristmasBackground />

      <div className="max-w-md w-full mx-4 relative z-10">
        <div className="bg-white/95 backdrop-blur-sm rounded-2xl shadow-2xl p-8 border-4 border-red-600/20">
          {/* Decorative ribbon */}
          <div className="absolute -top-4 left-1/2 transform -translate-x-1/2 bg-red-600 text-white px-6 py-2 rounded-full shadow-lg">
            <span className="text-sm font-bold">🎄 Ho Ho Ho! 🎄</span>
          </div>

          <div className="text-center mb-8 mt-4">
            <h1 className="text-5xl font-bold mb-2 bg-gradient-to-r from-red-600 to-green-600 bg-clip-text text-transparent">
              🎅 Secret Santa 🎁
            </h1>
            <p className="text-gray-700 font-medium">Sign in to discover your assignment!</p>
            <div className="mt-2 text-2xl">✨ 🌟 ✨</div>
          </div>

          <form onSubmit={handleLogin} className="space-y-6">
            <div>
              <label
                htmlFor="email"
                className="block text-sm font-bold text-gray-700 mb-2"
              >
                📧 Email Address
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-4 py-3 border-2 border-red-200 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-red-500 transition-all"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="block text-sm font-bold text-gray-700 mb-2"
              >
                🔐 Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full px-4 py-3 border-2 border-red-200 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-red-500 transition-all"
                placeholder="••••••••"
              />
            </div>

            {error && (
              <div className="bg-red-50 border-2 border-red-300 text-red-700 px-4 py-3 rounded-lg">
                <span className="font-semibold">❌ {error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-gradient-to-r from-red-600 to-green-600 hover:from-red-700 hover:to-green-700 text-white font-bold py-4 px-4 rounded-lg transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg hover:shadow-xl transform hover:-translate-y-0.5"
            >
              {loading ? '🎄 Signing in...' : '🎁 Sign In to Unwrap'}
            </button>
          </form>

          <div className="mt-6 text-center text-sm text-gray-600">
            <p className="bg-green-50 border border-green-200 rounded-lg p-3">
              🎅 Need help? Contact your Secret Santa administrator!
            </p>
          </div>
        </div>

        {/* Decorative presents */}
        <div className="absolute -bottom-8 -left-8 text-6xl animate-bounce" style={{ animationDuration: '3s' }}>
          🎁
        </div>
        <div className="absolute -bottom-8 -right-8 text-6xl animate-bounce" style={{ animationDuration: '2.5s', animationDelay: '0.5s' }}>
          🎁
        </div>
      </div>
    </div>
  )
}

'use client'

import { useState } from 'react'

export default function AdminPage() {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleGenerateAssignments = async () => {
    setLoading(true)
    setResult(null)
    setError(null)

    try {
      const response = await fetch('/api/admin/generate-assignments', {
        method: 'POST',
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || 'Failed to generate assignments')
      }

      setResult(JSON.stringify(data, null, 2))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const handleSendNotifications = async () => {
    setLoading(true)
    setResult(null)
    setError(null)

    try {
      const response = await fetch('/api/admin/send-notifications', {
        method: 'POST',
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || 'Failed to send notifications')
      }

      setResult(JSON.stringify(data, null, 2))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-red-50 via-white to-green-50 p-8">
      <div className="max-w-4xl mx-auto">
        <div className="bg-white rounded-lg shadow-xl p-8">
          <h1 className="text-3xl font-bold text-red-600 mb-2">
            🎅 Secret Santa Admin
          </h1>
          <p className="text-gray-600 mb-8">
            Manage Secret Santa assignments and notifications
          </p>

          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-8">
            <p className="text-sm text-yellow-800">
              <strong>⚠️ Warning:</strong> This page should be protected in production.
              Anyone with access can regenerate assignments and send notifications.
            </p>
          </div>

          <div className="space-y-6">
            {/* Generate Assignments */}
            <div className="border border-gray-200 rounded-lg p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-3">
                Generate Assignments
              </h2>
              <p className="text-gray-600 mb-4">
                This will create new Secret Santa assignments based on the participants
                defined in <code className="bg-gray-100 px-2 py-1 rounded">lib/participants.ts</code>.
                It will respect the couples configuration to ensure couples don't get each other.
              </p>
              <p className="text-sm text-gray-500 mb-4">
                <strong>Note:</strong> This will delete and regenerate all assignments for the current year.
              </p>
              <button
                onClick={handleGenerateAssignments}
                disabled={loading}
                className="px-6 py-3 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? 'Generating...' : 'Generate Assignments'}
              </button>
            </div>

            {/* Send Notifications */}
            <div className="border border-gray-200 rounded-lg p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-3">
                Send Notifications
              </h2>
              <p className="text-gray-600 mb-4">
                Send assignment notification emails to all participants.
              </p>
              <p className="text-sm text-orange-600 mb-4">
                <strong>⚠️ Email Stub Mode:</strong> Emails are currently stubbed and will only
                log to the console. To send real emails, update <code className="bg-gray-100 px-2 py-1 rounded">lib/email.ts</code>
                with your email service provider.
              </p>
              <button
                onClick={handleSendNotifications}
                disabled={loading}
                className="px-6 py-3 bg-green-600 hover:bg-green-700 text-white font-semibold rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? 'Sending...' : 'Send Notifications (Stub)'}
              </button>
            </div>

            {/* Results */}
            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <h3 className="text-red-800 font-semibold mb-2">Error</h3>
                <pre className="text-sm text-red-700 whitespace-pre-wrap">{error}</pre>
              </div>
            )}

            {result && (
              <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                <h3 className="text-green-800 font-semibold mb-2">Success</h3>
                <pre className="text-sm text-green-700 whitespace-pre-wrap overflow-x-auto">
                  {result}
                </pre>
              </div>
            )}
          </div>

          <div className="mt-8 pt-8 border-t border-gray-200">
            <h3 className="text-lg font-semibold text-gray-900 mb-3">
              Quick Links
            </h3>
            <ul className="space-y-2 text-sm">
              <li>
                <a href="/dashboard" className="text-blue-600 hover:underline">
                  → Go to Dashboard
                </a>
              </li>
              <li>
                <a href="/login" className="text-blue-600 hover:underline">
                  → Go to Login
                </a>
              </li>
              <li>
                <span className="text-gray-600">
                  Edit participants:{' '}
                  <code className="bg-gray-100 px-2 py-1 rounded text-xs">
                    lib/participants.ts
                  </code>
                </span>
              </li>
              <li>
                <span className="text-gray-600">
                  Database schema:{' '}
                  <code className="bg-gray-100 px-2 py-1 rounded text-xs">
                    DATABASE_SCHEMA.md
                  </code>
                </span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

import { NextResponse } from 'next/server'
import { sendAssignmentEmail } from '@/lib/email'
import { getAllAssignmentsForYear } from '@/lib/db/queries'

/**
 * Admin endpoint to send assignment notification emails
 * This uses stubbed email functionality (logs to console)
 */
export async function POST() {
  try {
    const year = new Date().getFullYear()

    // Get all assignments with profile data
    const assignments = getAllAssignmentsForYear(year)

    if (!assignments || assignments.length === 0) {
      return NextResponse.json(
        { error: 'No assignments found for this year' },
        { status: 404 }
      )
    }

    // Send emails to all participants
    const emailResults = []

    for (const assignment of assignments) {
      const success = await sendAssignmentEmail(
        (assignment as any).giver_email,
        (assignment as any).giver_full_name,
        (assignment as any).receiver_full_name
      )

      emailResults.push({
        to: (assignment as any).giver_email,
        success,
      })
    }

    return NextResponse.json({
      success: true,
      message: `Sent ${emailResults.length} notification emails (stubbed - check console)`,
      results: emailResults,
    })
  } catch (error) {
    console.error('Error sending notifications:', error)
    return NextResponse.json(
      { error: 'Internal server error', details: String(error) },
      { status: 500 }
    )
  }
}

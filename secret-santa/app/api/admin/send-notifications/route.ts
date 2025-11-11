import { NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'
import { sendAssignmentEmail } from '@/lib/email'

/**
 * Admin endpoint to send assignment notification emails
 * This uses stubbed email functionality (logs to console)
 */
export async function POST() {
  try {
    const supabase = await createClient()
    const year = new Date().getFullYear()

    // Get all assignments with profile data
    const { data: assignments, error } = await supabase
      .from('assignments')
      .select(`
        *,
        giver:profiles!assignments_giver_id_fkey(id, email, full_name),
        receiver:profiles!assignments_receiver_id_fkey(id, email, full_name)
      `)
      .eq('year', year)

    if (error) {
      return NextResponse.json(
        { error: 'Failed to fetch assignments', details: error },
        { status: 500 }
      )
    }

    if (!assignments || assignments.length === 0) {
      return NextResponse.json(
        { error: 'No assignments found for this year' },
        { status: 404 }
      )
    }

    // Send emails to all participants
    const emailResults = []

    for (const assignment of assignments) {
      const giver = assignment.giver as any
      const receiver = assignment.receiver as any

      const success = await sendAssignmentEmail(
        giver.email,
        giver.full_name,
        receiver.full_name
      )

      emailResults.push({
        to: giver.email,
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

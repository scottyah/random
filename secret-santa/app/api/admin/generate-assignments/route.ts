import { NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'
import { participants } from '@/lib/participants'
import {
  generateSecretSantaAssignments,
  validateAssignments,
} from '@/lib/secret-santa-algorithm'

/**
 * Admin endpoint to generate Secret Santa assignments
 * This should be protected in production or run manually
 */
export async function POST() {
  try {
    const supabase = await createClient()

    // Generate assignments using the algorithm
    const assignments = generateSecretSantaAssignments(participants)

    if (!assignments) {
      return NextResponse.json(
        { error: 'Could not generate valid assignments. Please check your participants and couples configuration.' },
        { status: 400 }
      )
    }

    // Validate assignments
    const validation = validateAssignments(participants, assignments)
    if (!validation.valid) {
      return NextResponse.json(
        { error: 'Invalid assignments generated', details: validation.errors },
        { status: 400 }
      )
    }

    // Get current year
    const year = new Date().getFullYear()

    // Delete existing assignments for this year
    const { error: deleteError } = await supabase
      .from('assignments')
      .delete()
      .eq('year', year)

    if (deleteError) {
      console.error('Error deleting old assignments:', deleteError)
    }

    // Store assignments in database
    const assignmentRecords = []

    for (const assignment of assignments) {
      // Get profile IDs for giver and receiver
      const { data: giverProfile } = await supabase
        .from('profiles')
        .select('id')
        .eq('email', assignment.giver.email)
        .single()

      const { data: receiverProfile } = await supabase
        .from('profiles')
        .select('id')
        .eq('email', assignment.receiver.email)
        .single()

      if (giverProfile && receiverProfile) {
        assignmentRecords.push({
          giver_id: giverProfile.id,
          receiver_id: receiverProfile.id,
          year,
        })
      }
    }

    // Insert all assignments
    const { data, error } = await supabase
      .from('assignments')
      .insert(assignmentRecords)
      .select()

    if (error) {
      return NextResponse.json(
        { error: 'Failed to save assignments', details: error },
        { status: 500 }
      )
    }

    return NextResponse.json({
      success: true,
      message: `Generated ${assignments.length} Secret Santa assignments for ${year}`,
      assignments: assignments.map((a) => ({
        giver: a.giver.name,
        receiver: a.receiver.name,
      })),
    })
  } catch (error) {
    console.error('Error generating assignments:', error)
    return NextResponse.json(
      { error: 'Internal server error', details: String(error) },
      { status: 500 }
    )
  }
}

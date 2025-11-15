import { NextResponse } from 'next/server'
import { participants } from '@/lib/participants'
import {
  generateSecretSantaAssignments,
  validateAssignments,
} from '@/lib/secret-santa-algorithm'
import { getUserByEmail, createAssignment, deleteAssignmentsForYear } from '@/lib/db/queries'

/**
 * Admin endpoint to generate Secret Santa assignments
 * This should be protected in production or run manually
 */
export async function POST() {
  try {
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
    deleteAssignmentsForYear(year)

    // Store assignments in database
    const savedAssignments = []

    for (const assignment of assignments) {
      // Get user IDs for giver and receiver
      const giver = getUserByEmail(assignment.giver.email)
      const receiver = getUserByEmail(assignment.receiver.email)

      if (giver && receiver) {
        createAssignment(giver.id, receiver.id, year)
        savedAssignments.push({
          giver: assignment.giver.name,
          receiver: assignment.receiver.name,
        })
      } else {
        console.warn(
          `Could not create assignment: ${assignment.giver.email} -> ${assignment.receiver.email}. Users not found.`
        )
      }
    }

    return NextResponse.json({
      success: true,
      message: `Generated ${savedAssignments.length} Secret Santa assignments for ${year}`,
      assignments: savedAssignments,
    })
  } catch (error) {
    console.error('Error generating assignments:', error)
    return NextResponse.json(
      { error: 'Internal server error', details: String(error) },
      { status: 500 }
    )
  }
}

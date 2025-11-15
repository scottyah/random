import { NextResponse } from 'next/server'
import { participants, areCouples } from '@/lib/participants'
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

    // Store assignments in database and track validation info
    const givers = new Set<string>()
    const receivers = new Set<string>()
    let coupleViolationCount = 0
    let savedCount = 0
    let skippedCount = 0

    for (const assignment of assignments) {
      // Get user IDs for giver and receiver
      const giver = getUserByEmail(assignment.giver.email)
      const receiver = getUserByEmail(assignment.receiver.email)

      if (giver && receiver) {
        createAssignment(giver.id, receiver.id, year)
        givers.add(assignment.giver.name)
        receivers.add(assignment.receiver.name)
        savedCount++

        // Check for couple violations (don't log names to protect privacy)
        if (areCouples(assignment.giver.email, assignment.receiver.email)) {
          coupleViolationCount++
        }
      } else {
        skippedCount++
        // Don't log specific emails to protect assignment privacy
        console.warn('Could not create assignment: one or more users not found in database')
      }
    }

    // Build validation summary
    const validationSummary = {
      totalParticipants: participants.length,
      assignmentsCreated: savedCount,
      assignmentsSkipped: skippedCount,
      uniqueGivers: givers.size,
      uniqueReceivers: receivers.size,
      allParticipantsGiveOnce: givers.size === savedCount,
      allParticipantsReceiveOnce: receivers.size === savedCount,
      noCoupleViolations: coupleViolationCount === 0,
    }

    // Check for issues
    const issues: string[] = []
    if (skippedCount > 0) {
      issues.push(`${skippedCount} assignments skipped (users not found in database)`)
    }
    if (!validationSummary.allParticipantsGiveOnce) {
      issues.push('Not all participants are giving exactly once')
    }
    if (!validationSummary.allParticipantsReceiveOnce) {
      issues.push('Not all participants are receiving exactly once')
    }
    if (coupleViolationCount > 0) {
      issues.push(`${coupleViolationCount} couple violation(s) found`)
    }

    return NextResponse.json({
      success: issues.length === 0,
      message: `Generated ${savedCount} Secret Santa assignments for ${year}`,
      validation: validationSummary,
      issues: issues.length > 0 ? issues : undefined,
    })
  } catch (error) {
    console.error('Error generating assignments:', error)
    return NextResponse.json(
      { error: 'Internal server error', details: String(error) },
      { status: 500 }
    )
  }
}

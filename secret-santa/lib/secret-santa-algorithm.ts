import { areCouples } from './participants'

export interface Participant {
  email: string
  name: string
}

export interface Assignment {
  giver: Participant
  receiver: Participant
}

/**
 * Shuffles an array using Fisher-Yates algorithm
 */
function shuffle<T>(array: T[]): T[] {
  const shuffled = [...array]
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]]
  }
  return shuffled
}

/**
 * Checks if a given assignment is valid (not themselves, not their partner)
 */
function isValidAssignment(giver: Participant, receiver: Participant): boolean {
  if (giver.email === receiver.email) return false
  if (areCouples(giver.email, receiver.email)) return false
  return true
}

/**
 * Generates Secret Santa assignments ensuring:
 * 1. Nobody gets themselves
 * 2. Couples don't get each other
 * 3. Everyone gives to exactly one person and receives from exactly one person
 *
 * Uses a backtracking algorithm to find a valid assignment
 */
export function generateSecretSantaAssignments(
  participants: Participant[],
  maxAttempts: number = 1000
): Assignment[] | null {
  if (participants.length < 2) {
    throw new Error('Need at least 2 participants for Secret Santa')
  }

  // Try multiple times to find a valid assignment
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const shuffled = shuffle(participants)
    const assignments: Assignment[] = []
    let valid = true

    // Create a circular assignment (each person gives to the next)
    for (let i = 0; i < shuffled.length; i++) {
      const giver = shuffled[i]
      const receiver = shuffled[(i + 1) % shuffled.length]

      if (!isValidAssignment(giver, receiver)) {
        valid = false
        break
      }

      assignments.push({ giver, receiver })
    }

    if (valid) {
      return assignments
    }
  }

  // If we couldn't find a valid assignment, try a more sophisticated approach
  return generateAssignmentsWithBacktracking(participants)
}

/**
 * More sophisticated backtracking algorithm for cases where simple shuffling doesn't work
 */
function generateAssignmentsWithBacktracking(
  participants: Participant[]
): Assignment[] | null {
  const n = participants.length
  const givers = [...participants]
  const receivers = [...participants]
  const assignments: Assignment[] = []
  const used = new Set<string>()

  function backtrack(index: number): boolean {
    if (index === n) {
      return true
    }

    const giver = givers[index]

    // Try each unused receiver
    for (let i = 0; i < n; i++) {
      const receiver = receivers[i]

      if (used.has(receiver.email)) continue
      if (!isValidAssignment(giver, receiver)) continue

      // Try this assignment
      used.add(receiver.email)
      assignments.push({ giver, receiver })

      if (backtrack(index + 1)) {
        return true
      }

      // Backtrack
      used.delete(receiver.email)
      assignments.pop()
    }

    return false
  }

  // Shuffle to get different results each time
  const shuffledGivers = shuffle(givers)
  givers.splice(0, givers.length, ...shuffledGivers)

  if (backtrack(0)) {
    return assignments
  }

  return null
}

/**
 * Validates that all assignments are correct:
 * - Everyone gives to exactly one person
 * - Everyone receives from exactly one person
 * - No one gives to themselves or their partner
 */
export function validateAssignments(
  participants: Participant[],
  assignments: Assignment[]
): { valid: boolean; errors: string[] } {
  const errors: string[] = []

  // Check count
  if (assignments.length !== participants.length) {
    errors.push(
      `Assignment count mismatch: expected ${participants.length}, got ${assignments.length}`
    )
  }

  // Check all participants are givers
  const givers = new Set(assignments.map((a) => a.giver.email))
  const receivers = new Set(assignments.map((a) => a.receiver.email))

  for (const participant of participants) {
    if (!givers.has(participant.email)) {
      errors.push(`${participant.name} is not giving to anyone`)
    }
    if (!receivers.has(participant.email)) {
      errors.push(`${participant.name} is not receiving from anyone`)
    }
  }

  // Check for invalid assignments
  for (const assignment of assignments) {
    if (!isValidAssignment(assignment.giver, assignment.receiver)) {
      errors.push(
        `Invalid assignment: ${assignment.giver.name} cannot give to ${assignment.receiver.name}`
      )
    }
  }

  return {
    valid: errors.length === 0,
    errors,
  }
}

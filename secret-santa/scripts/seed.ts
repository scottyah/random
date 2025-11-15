import { createUser, getUserByEmail } from '../lib/db/queries'
import { participants } from '../lib/participants'

/**
 * Seed script to create users from the participants list
 * Run with: npx ts-node scripts/seed.ts
 */

const DEFAULT_PASSWORD = 'secretsanta123'

async function seed() {
  console.log('🎄 Starting Secret Santa database seed...')
  console.log(`Creating ${participants.length} users with default password: ${DEFAULT_PASSWORD}`)
  console.log('')

  for (const participant of participants) {
    try {
      // Check if user already exists
      const existingUser = getUserByEmail(participant.email)

      if (existingUser) {
        console.log(`⏩ User ${participant.email} already exists, skipping`)
        continue
      }

      // Create new user
      const user = createUser(participant.email, participant.name, DEFAULT_PASSWORD)
      console.log(`✅ Created user: ${participant.name} (${participant.email})`)
    } catch (error) {
      console.error(`❌ Failed to create user ${participant.email}:`, error)
    }
  }

  console.log('')
  console.log('🎅 Seed complete!')
  console.log('')
  console.log('Next steps:')
  console.log('1. Start the dev server: npm run dev')
  console.log('2. Go to http://localhost:3000/admin')
  console.log('3. Click "Generate Assignments"')
  console.log('4. Users can login with their email and password:', DEFAULT_PASSWORD)
}

seed().catch(console.error)

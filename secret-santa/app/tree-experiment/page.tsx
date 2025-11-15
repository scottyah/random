'use client'

import { useEffect, useRef, useState } from 'react'

interface Point {
  x: number
  y: number
  originalX: number
  originalY: number
}

interface Edge {
  start: number
  end: number
}

interface Tree {
  id: number
  x: number
  y: number
  rotation: number
  rotationSpeed: number
  fallSpeed: number
  scale: number
  points: Point[]
}

// Create a geodesic/triangulated tree shape
function createTreePoints(centerX: number, centerY: number, scale: number): Point[] {
  const points: Point[] = []

  // Tree trunk bottom
  points.push({ x: centerX - 8 * scale, y: centerY + 100 * scale, originalX: centerX - 8 * scale, originalY: centerY + 100 * scale })
  points.push({ x: centerX + 8 * scale, y: centerY + 100 * scale, originalX: centerX + 8 * scale, originalY: centerY + 100 * scale })

  // Tree trunk top
  points.push({ x: centerX - 8 * scale, y: centerY + 50 * scale, originalX: centerX - 8 * scale, originalY: centerY + 50 * scale })
  points.push({ x: centerX + 8 * scale, y: centerY + 50 * scale, originalX: centerX + 8 * scale, originalY: centerY + 50 * scale })

  // Bottom tier
  points.push({ x: centerX - 45 * scale, y: centerY + 50 * scale, originalX: centerX - 45 * scale, originalY: centerY + 50 * scale })
  points.push({ x: centerX + 45 * scale, y: centerY + 50 * scale, originalX: centerX + 45 * scale, originalY: centerY + 50 * scale })
  points.push({ x: centerX, y: centerY + 10 * scale, originalX: centerX, originalY: centerY + 10 * scale })

  // Middle tier
  points.push({ x: centerX - 35 * scale, y: centerY + 10 * scale, originalX: centerX - 35 * scale, originalY: centerY + 10 * scale })
  points.push({ x: centerX + 35 * scale, y: centerY + 10 * scale, originalX: centerX + 35 * scale, originalY: centerY + 10 * scale })
  points.push({ x: centerX, y: centerY - 35 * scale, originalX: centerX, originalY: centerY - 35 * scale })

  // Top tier
  points.push({ x: centerX - 25 * scale, y: centerY - 35 * scale, originalX: centerX - 25 * scale, originalY: centerY - 35 * scale })
  points.push({ x: centerX + 25 * scale, y: centerY - 35 * scale, originalX: centerX + 25 * scale, originalY: centerY - 35 * scale })
  points.push({ x: centerX, y: centerY - 80 * scale, originalX: centerX, originalY: centerY - 80 * scale })

  // Star on top
  points.push({ x: centerX, y: centerY - 95 * scale, originalX: centerX, originalY: centerY - 95 * scale })

  return points
}

// Define edges connecting the points
const treeEdges: Edge[] = [
  // Trunk
  { start: 0, end: 1 },
  { start: 0, end: 2 },
  { start: 1, end: 3 },
  { start: 2, end: 3 },

  // Bottom tier triangles
  { start: 4, end: 5 },
  { start: 4, end: 6 },
  { start: 5, end: 6 },
  { start: 2, end: 4 },
  { start: 3, end: 5 },

  // Middle tier triangles
  { start: 7, end: 8 },
  { start: 7, end: 9 },
  { start: 8, end: 9 },
  { start: 6, end: 7 },
  { start: 6, end: 8 },

  // Top tier triangles
  { start: 10, end: 11 },
  { start: 10, end: 12 },
  { start: 11, end: 12 },
  { start: 9, end: 10 },
  { start: 9, end: 11 },

  // Star
  { start: 12, end: 13 },
]

export default function TreeExperiment() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const treesRef = useRef<Tree[]>([])
  const mousePos = useRef({ x: 0, y: 0 })
  const animationRef = useRef<number>()
  const initialized = useRef(false)

  // Initialize trees
  useEffect(() => {
    if (initialized.current) return
    initialized.current = true

    const initialTrees: Tree[] = []
    for (let i = 0; i < 10; i++) {
      const x = Math.random() * window.innerWidth
      const y = -200 - Math.random() * 600
      const scale = 0.8 + Math.random() * 0.4
      initialTrees.push({
        id: i,
        x,
        y,
        rotation: Math.random() * 360,
        rotationSpeed: (Math.random() - 0.5) * 0.5,
        fallSpeed: 0.125 + Math.random() * 0.25,
        scale,
        points: createTreePoints(0, 0, scale),
      })
    }
    treesRef.current = initialTrees
  }, [])

  // Handle mouse movement
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      mousePos.current = { x: e.clientX, y: e.clientY }
    }

    window.addEventListener('mousemove', handleMouseMove)
    return () => window.removeEventListener('mousemove', handleMouseMove)
  }, [])

  // Animation loop
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const resizeCanvas = () => {
      canvas.width = window.innerWidth
      canvas.height = window.innerHeight
    }

    resizeCanvas()
    window.addEventListener('resize', resizeCanvas)

    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      treesRef.current.forEach((tree) => {
        // Update tree position (falling)
        tree.y += tree.fallSpeed
        tree.rotation += tree.rotationSpeed

        // Reset tree if it falls off screen
        if (tree.y > canvas.height + 200) {
          tree.y = -200
          tree.x = Math.random() * canvas.width
        }

        // Update points based on mouse proximity
        tree.points.forEach((point) => {
          // Transform point to world coordinates
          const rad = (tree.rotation * Math.PI) / 180
          const cos = Math.cos(rad)
          const sin = Math.sin(rad)

          const worldX = tree.x + point.originalX * cos - point.originalY * sin
          const worldY = tree.y + point.originalX * sin + point.originalY * cos

          // Calculate distance to mouse
          const dx = worldX - mousePos.current.x
          const dy = worldY - mousePos.current.y
          const dist = Math.sqrt(dx * dx + dy * dy)

          // Repel from mouse
          const repelRadius = 150
          const repelStrength = 30

          if (dist < repelRadius && dist > 0) {
            const force = ((repelRadius - dist) / repelRadius) * repelStrength
            const angle = Math.atan2(dy, dx)

            // Move away from mouse in local coordinates
            const targetX = point.originalX + Math.cos(angle) * force
            const targetY = point.originalY + Math.sin(angle) * force

            // Smooth interpolation
            point.x = point.x + (targetX - point.x) * 0.3
            point.y = point.y + (targetY - point.y) * 0.3
          } else {
            // Return to original position
            point.x = point.x + (point.originalX - point.x) * 0.1
            point.y = point.y + (point.originalY - point.y) * 0.1
          }
        })

        // Draw tree
        ctx.save()
        ctx.translate(tree.x, tree.y)
        ctx.rotate((tree.rotation * Math.PI) / 180)

        // Draw edges
        ctx.strokeStyle = '#2d5a27'
        ctx.lineWidth = 2
        ctx.lineCap = 'round'

        treeEdges.forEach((edge) => {
          const start = tree.points[edge.start]
          const end = tree.points[edge.end]

          ctx.beginPath()
          ctx.moveTo(start.x, start.y)
          ctx.lineTo(end.x, end.y)
          ctx.stroke()
        })

        // Draw points (ornaments)
        tree.points.forEach((point, i) => {
          if (i === 13) {
            // Star with luminous rays
            const starX = point.x
            const starY = point.y

            // Draw glowing rays behind the star
            ctx.save()
            const rayCount = 8
            const rayLength = 20
            const innerRayLength = 12

            for (let r = 0; r < rayCount; r++) {
              const angle = (r / rayCount) * Math.PI * 2 - Math.PI / 2
              const gradient = ctx.createLinearGradient(
                starX,
                starY,
                starX + Math.cos(angle) * rayLength,
                starY + Math.sin(angle) * rayLength
              )
              gradient.addColorStop(0, 'rgba(255, 215, 0, 0.8)')
              gradient.addColorStop(1, 'rgba(255, 215, 0, 0)')

              ctx.beginPath()
              ctx.moveTo(starX, starY)
              ctx.lineTo(
                starX + Math.cos(angle - 0.1) * innerRayLength,
                starY + Math.sin(angle - 0.1) * innerRayLength
              )
              ctx.lineTo(
                starX + Math.cos(angle) * rayLength,
                starY + Math.sin(angle) * rayLength
              )
              ctx.lineTo(
                starX + Math.cos(angle + 0.1) * innerRayLength,
                starY + Math.sin(angle + 0.1) * innerRayLength
              )
              ctx.closePath()
              ctx.fillStyle = gradient
              ctx.fill()
            }
            ctx.restore()

            // Draw 5-pointed star
            ctx.beginPath()
            const outerRadius = 8
            const innerRadius = 4
            for (let s = 0; s < 5; s++) {
              const outerAngle = (s / 5) * Math.PI * 2 - Math.PI / 2
              const innerAngle = ((s + 0.5) / 5) * Math.PI * 2 - Math.PI / 2

              if (s === 0) {
                ctx.moveTo(
                  starX + Math.cos(outerAngle) * outerRadius,
                  starY + Math.sin(outerAngle) * outerRadius
                )
              } else {
                ctx.lineTo(
                  starX + Math.cos(outerAngle) * outerRadius,
                  starY + Math.sin(outerAngle) * outerRadius
                )
              }
              ctx.lineTo(
                starX + Math.cos(innerAngle) * innerRadius,
                starY + Math.sin(innerAngle) * innerRadius
              )
            }
            ctx.closePath()
            ctx.fillStyle = '#ffd700'
            ctx.fill()
            ctx.strokeStyle = '#ffed4a'
            ctx.lineWidth = 1
            ctx.stroke()
          } else {
            ctx.beginPath()
            ctx.arc(point.x, point.y, 3, 0, Math.PI * 2)

            if (i < 4) {
              // Trunk - dark brown
              ctx.fillStyle = '#3d2817'
            } else {
              // Tree body - very dark green
              ctx.fillStyle = '#0d3311'
            }
            ctx.fill()
          }
        })

        ctx.restore()
      })

      animationRef.current = requestAnimationFrame(animate)
    }

    animate()

    return () => {
      window.removeEventListener('resize', resizeCanvas)
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current)
      }
    }
  }, [])

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 to-gray-800 relative overflow-hidden">
      <canvas
        ref={canvasRef}
        className="absolute inset-0"
      />

      <div className="relative z-10 p-8">
        <h1 className="text-4xl font-bold text-white mb-4">
          Interactive Geodesic Trees
        </h1>
        <p className="text-gray-300 max-w-xl">
          Move your mouse around to watch the tree edges avoid your cursor!
          The trees fall and rotate gently while their edges react to your mouse position.
        </p>

        <a
          href="/dashboard"
          className="inline-block mt-6 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg transition"
        >
          Back to Dashboard
        </a>
      </div>
    </div>
  )
}

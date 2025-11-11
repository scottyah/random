'use client'

import { useEffect, useState } from 'react'

interface Snowflake {
  id: number
  left: number
  size: number
  duration: number
  delay: number
}

export default function ChristmasBackground() {
  const [snowflakes, setSnowflakes] = useState<Snowflake[]>([])

  useEffect(() => {
    // Generate snowflakes
    const flakes: Snowflake[] = Array.from({ length: 50 }, (_, i) => ({
      id: i,
      left: Math.random() * 100,
      size: Math.random() * 3 + 2,
      duration: Math.random() * 10 + 15,
      delay: Math.random() * 5,
    }))
    setSnowflakes(flakes)
  }, [])

  return (
    <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
      {/* Christmas lights at the top */}
      <div className="absolute top-0 left-0 right-0 h-8 flex justify-around items-center">
        {Array.from({ length: 20 }).map((_, i) => (
          <div
            key={i}
            className="w-3 h-3 rounded-full"
            style={{
              backgroundColor: ['#ff0000', '#00ff00', '#ffff00', '#ff00ff', '#00ffff'][i % 5],
              animation: `pulse-glow ${1 + (i % 3)}s infinite`,
              animationDelay: `${i * 0.1}s`,
            }}
          />
        ))}
      </div>

      {/* Snowflakes */}
      {snowflakes.map((flake) => (
        <div
          key={flake.id}
          className="absolute text-white opacity-80"
          style={{
            left: `${flake.left}%`,
            fontSize: `${flake.size}px`,
            animation: `snowfall ${flake.duration}s linear infinite`,
            animationDelay: `${flake.delay}s`,
          }}
        >
          ❄
        </div>
      ))}
    </div>
  )
}

// Lightweight Apple/SF-Symbols-style line icons. Stroke = currentColor so they
// inherit the surrounding text color. Single responsibility: presentational SVGs.
import React from 'react'

type IconProps = { size?: number }

function Svg({ size = 18, children }: { size?: number; children: React.ReactNode }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {children}
    </svg>
  )
}

export const IconNewChat = ({ size }: IconProps) => (
  <Svg size={size}>
    <path d="M20 11.5V17a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3V7a3 3 0 0 1 3-3h5.5" />
    <path d="M18.4 3.6a1.9 1.9 0 0 1 2.7 2.7L13 14.4l-3.5.8.8-3.5 8.1-8.1z" />
  </Svg>
)

export const IconProjects = ({ size }: IconProps) => (
  <Svg size={size}>
    <path d="M3 7a2 2 0 0 1 2-2h3.4a2 2 0 0 1 1.4.6L11 7h6a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z" />
  </Svg>
)

export const IconAgents = ({ size }: IconProps) => (
  <Svg size={size}>
    <circle cx="12" cy="12" r="9" />
    <circle cx="12" cy="10" r="3" />
    <path d="M6.5 18.4a6 6 0 0 1 11 0" />
  </Svg>
)

export const IconUsers = ({ size }: IconProps) => (
  <Svg size={size}>
    <circle cx="9" cy="8" r="3.2" />
    <path d="M2.8 19a6.2 6.2 0 0 1 12.4 0" />
    <path d="M16 5.4a3 3 0 0 1 0 5.6" />
    <path d="M17.4 13.2a5.5 5.5 0 0 1 3.8 5.6" />
  </Svg>
)

export const IconGear = ({ size }: IconProps) => (
  <Svg size={size}>
    <circle cx="12" cy="12" r="3.2" />
    <path d="M19.4 13a7.6 7.6 0 0 0 0-2l2-1.5-2-3.5-2.4 1a7.6 7.6 0 0 0-1.7-1L15 3h-4l-.3 2.5a7.6 7.6 0 0 0-1.7 1l-2.4-1-2 3.5 2 1.5a7.6 7.6 0 0 0 0 2l-2 1.5 2 3.5 2.4-1a7.6 7.6 0 0 0 1.7 1L11 21h4l.3-2.5a7.6 7.6 0 0 0 1.7-1l2.4 1 2-3.5z" />
  </Svg>
)

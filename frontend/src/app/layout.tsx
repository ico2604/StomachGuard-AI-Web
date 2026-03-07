/**
 * 루트 레이아웃
 */

import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: '위암 분류 병원 관리 시스템',
  description: 'AI 기반 위암 진단 시스템',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ko">
      <body className="min-h-screen bg-gray-50">
        {children}
      </body>
    </html>
  )
}

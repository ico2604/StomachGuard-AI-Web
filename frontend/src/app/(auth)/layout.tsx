'use client'

import { useEffect, useState, useRef, useCallback } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import api from '@/lib/api'

export default function AuthenticatedLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const router = useRouter()
  const pathname = usePathname()
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isChecking, setIsChecking] = useState(true)
  const hasChecked = useRef(false)

  const logout = useCallback(() => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('user')
    hasChecked.current = false
    setIsAuthenticated(false)
    router.replace('/login')
  }, [router])

  useEffect(() => {
    // 이미 인증 확인이 완료된 경우 페이지 이동 시 재확인하지 않음
    if (hasChecked.current && isAuthenticated) {
      setIsChecking(false)
      return
    }

    const checkAuth = async () => {
      const token = localStorage.getItem('access_token')

      if (!token) {
        console.log('[Auth] 토큰 없음 -> 로그인')
        router.replace('/login')
        return
      }

      try {
        const userData = await api.getCurrentUser()
        localStorage.setItem('user', JSON.stringify(userData))
        hasChecked.current = true
        setIsAuthenticated(true)
        setIsChecking(false)
      } catch (err: any) {
        console.error('[Auth] 인증 실패:', err?.response?.status)
        logout()
      }
    }

    // 로그인 직후 localStorage 저장 완료를 보장하기 위한 지연
    const timer = setTimeout(checkAuth, 50)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // 의존성 빈 배열: 최초 마운트 시 1회만 실행

  // 다른 탭에서 토큰이 삭제되면 로그아웃 처리
  useEffect(() => {
    const handleStorage = (e: StorageEvent) => {
      if (e.key === 'access_token' && !e.newValue) {
        logout()
      }
    }
    window.addEventListener('storage', handleStorage)
    return () => window.removeEventListener('storage', handleStorage)
  }, [logout])

  if (isChecking) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-white">
        <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
        <p className="mt-4 text-gray-600 font-medium">사용자 정보를 확인 중입니다...</p>
      </div>
    )
  }

  return <>{children}</>
}

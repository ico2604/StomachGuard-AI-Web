/** @type {import('next').NextConfig} */
const nextConfig = {
  // Docker standalone 출력 (프로덕션 빌드 최적화)
  output: 'standalone',

  // API 백엔드 프록시 설정 (개발 환경)
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*'
      }
    ]
  }
}

module.exports = nextConfig

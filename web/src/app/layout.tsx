import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'System-One: Đo lường kiểm soát ký ức agent AI',
  description: 'Công cụ đo lường thực nghiệm quyết định ký ức của agent trên các mô hình khác nhau',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi">
      <body className="min-h-screen bg-bg text-ink selection:bg-differ/20 selection:text-ink">
        {children}
      </body>
    </html>
  );
}

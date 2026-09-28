import type { Metadata } from 'next';
import localFont from 'next/font/local';
import './globals.css';
import { Toaster } from 'sonner';

const inter = localFont({
  src: './fonts/Inter-Variable.woff2',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'SPT Hospital HRMS',
  description: 'Hospital Attendance & Payroll Management',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.className} bg-slate-50 text-slate-900`}>
        {children}
        <Toaster />
      </body>
    </html>
  );
}

'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Home,
  UserPlus,
  ShieldCheck,
  Search,
  ScanFace,
  Activity,
  Users,
  Eye,
  Grid3X3,
  Video,
  MonitorPlay,
  LayoutDashboard,
  Webhook,
  Settings,
  Code,
  ChevronLeft,
  ChevronRight,
  X,
  GitCompare,
  Users2,
  Grid2X2,
  CreditCard,
  Database,
} from 'lucide-react';
import { cn } from '@/lib/utils/cn';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useAppStore } from '@/lib/store/app-store';
import { useTranslation } from 'react-i18next';

const navigationItems = [
  {
    title: 'nav.dashboard',
    href: '/',
    icon: Home,
    group: 'main',
  },
  {
    title: 'nav.enrollment',
    href: '/enrollment',
    icon: UserPlus,
    group: 'features',
  },
  {
    title: 'nav.verification',
    href: '/verification',
    icon: ShieldCheck,
    group: 'features',
  },
  {
    title: 'nav.search',
    href: '/search',
    icon: Search,
    group: 'features',
  },
  {
    title: 'nav.liveness',
    href: '/liveness',
    icon: ScanFace,
    group: 'features',
  },
  {
    title: 'nav.quality',
    href: '/quality',
    icon: Activity,
    group: 'features',
  },
  {
    title: 'nav.demographics',
    href: '/demographics',
    icon: Users,
    group: 'features',
  },
  {
    title: 'nav.landmarks',
    href: '/landmarks',
    icon: Eye,
    group: 'features',
  },
  {
    title: 'nav.comparison',
    href: '/comparison',
    icon: GitCompare,
    group: 'features',
  },
  {
    title: 'nav.multiFace',
    href: '/multi-face',
    icon: Users2,
    group: 'features',
  },
  {
    title: 'nav.similarity',
    href: '/similarity',
    icon: Grid2X2,
    group: 'features',
  },
  {
    title: 'nav.cardDetection',
    href: '/card-detection',
    icon: CreditCard,
    group: 'features',
  },
  {
    title: 'nav.batch',
    href: '/batch',
    icon: Grid3X3,
    group: 'features',
  },
  {
    title: 'nav.session',
    href: '/session',
    icon: Video,
    group: 'proctoring',
  },
  {
    title: 'nav.realtime',
    href: '/realtime',
    icon: MonitorPlay,
    group: 'proctoring',
  },
  {
    title: 'nav.admin',
    href: '/dashboard',
    icon: LayoutDashboard,
    group: 'admin',
  },
  {
    title: 'nav.webhooks',
    href: '/webhooks',
    icon: Webhook,
    group: 'admin',
  },
  {
    title: 'nav.embeddings',
    href: '/embeddings',
    icon: Database,
    group: 'admin',
  },
  {
    title: 'nav.apiExplorer',
    href: '/api-explorer',
    icon: Code,
    group: 'admin',
  },
  {
    title: 'nav.settings',
    href: '/settings',
    icon: Settings,
    group: 'settings',
  },
];

const groups = [
  { id: 'main', label: null },
  { id: 'features', label: 'Features' },
  { id: 'proctoring', label: 'Proctoring' },
  { id: 'admin', label: 'Admin' },
  { id: 'settings', label: null },
];

export function Sidebar() {
  const pathname = usePathname();
  const { t } = useTranslation();
  const { sidebarOpen, sidebarCollapsed, toggleSidebar, toggleSidebarCollapsed } = useAppStore();

  // Track mounted state to prevent hydration mismatches
  const [mounted, setMounted] = useState(false);
  const [isDesktop, setIsDesktop] = useState(false);

  useEffect(() => {
    setMounted(true);
    setIsDesktop(window.innerWidth >= 768);

    const handleResize = () => {
      setIsDesktop(window.innerWidth >= 768);
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Use consistent values during SSR to prevent hydration mismatch
  const width = mounted ? (sidebarCollapsed ? 64 : 256) : 256;
  const translateX = mounted ? (sidebarOpen || isDesktop ? 0 : -256) : 0;

  return (
    <>
      {/* Mobile overlay */}
      <AnimatePresence>
        {mounted && sidebarOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 bg-black/50 md:hidden"
            onClick={toggleSidebar}
          />
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <motion.aside
        initial={false}
        animate={{
          width,
          x: translateX,
        }}
        transition={{ duration: mounted ? 0.2 : 0, ease: 'easeInOut' }}
        className={cn(
          'fixed left-0 top-0 z-50 flex h-full flex-col border-r bg-background md:relative md:z-0',
          mounted && sidebarCollapsed ? 'w-16' : 'w-64'
        )}
      >
        {/* Logo */}
        <div className="flex h-14 items-center justify-between border-b px-4">
          <AnimatePresence mode="wait">
            {!(mounted && sidebarCollapsed) && (
              <motion.span
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="font-semibold text-foreground"
              >
                Biometric Demo
              </motion.span>
            )}
          </AnimatePresence>
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={toggleSidebar}
            aria-label="Close sidebar"
          >
            <X className="h-5 w-5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="hidden md:flex"
            onClick={toggleSidebarCollapsed}
            aria-label={mounted && sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {mounted && sidebarCollapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <ChevronLeft className="h-4 w-4" />
            )}
          </Button>
        </div>

        {/* Navigation */}
        <ScrollArea className="flex-1 py-4">
          <nav className="space-y-2 px-2">
            {groups.map((group) => {
              const groupItems = navigationItems.filter(
                (item) => item.group === group.id
              );
              if (groupItems.length === 0) return null;

              const isCollapsed = mounted && sidebarCollapsed;
              return (
                <div key={group.id} className="space-y-1">
                  {group.label && !isCollapsed && (
                    <p className="px-3 py-2 text-xs font-medium uppercase text-muted-foreground">
                      {group.label}
                    </p>
                  )}
                  {groupItems.map((item) => {
                    const isActive = pathname === item.href;
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        className={cn(
                          'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                          isActive
                            ? 'bg-primary text-primary-foreground'
                            : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                          isCollapsed && 'justify-center px-2'
                        )}
                        title={isCollapsed ? t(item.title) : undefined}
                      >
                        <item.icon className="h-4 w-4 shrink-0" />
                        {!isCollapsed && (
                          <span className="truncate">{t(item.title)}</span>
                        )}
                      </Link>
                    );
                  })}
                </div>
              );
            })}
          </nav>
        </ScrollArea>
      </motion.aside>
    </>
  );
}

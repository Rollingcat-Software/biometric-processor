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
  ChevronDown,
  X,
  GitCompare,
  Users2,
  Grid2X2,
  CreditCard,
  Database,
  Play,
  Sparkles,
} from 'lucide-react';
import { cn } from '@/lib/utils/cn';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useAppStore } from '@/lib/store/app-store';
import { useTranslation } from 'react-i18next';

const navigationItems = [
  // Main
  {
    title: 'nav.dashboard',
    href: '/',
    icon: Home,
    group: 'main',
  },
  {
    title: 'nav.guidedDemo',
    href: '/demo',
    icon: Sparkles,
    group: 'main',
    highlighted: true,
  },
  // Core Features
  {
    title: 'nav.enrollment',
    href: '/enrollment',
    icon: UserPlus,
    group: 'core',
  },
  {
    title: 'nav.verification',
    href: '/verification',
    icon: ShieldCheck,
    group: 'core',
  },
  {
    title: 'nav.liveness',
    href: '/liveness',
    icon: ScanFace,
    group: 'core',
  },
  {
    title: 'nav.search',
    href: '/search',
    icon: Search,
    group: 'core',
  },
  // Analysis
  {
    title: 'nav.quality',
    href: '/quality',
    icon: Activity,
    group: 'analysis',
  },
  {
    title: 'nav.demographics',
    href: '/demographics',
    icon: Users,
    group: 'analysis',
  },
  {
    title: 'nav.comparison',
    href: '/comparison',
    icon: GitCompare,
    group: 'analysis',
  },
  // Advanced
  {
    title: 'nav.landmarks',
    href: '/landmarks',
    icon: Eye,
    group: 'advanced',
  },
  {
    title: 'nav.multiFace',
    href: '/multi-face',
    icon: Users2,
    group: 'advanced',
  },
  {
    title: 'nav.similarity',
    href: '/similarity',
    icon: Grid2X2,
    group: 'advanced',
  },
  {
    title: 'nav.batch',
    href: '/batch',
    icon: Grid3X3,
    group: 'advanced',
  },
  {
    title: 'nav.cardDetection',
    href: '/card-detection',
    icon: CreditCard,
    group: 'advanced',
  },
  {
    title: 'nav.demo',
    href: '/unified-demo',
    icon: Play,
    group: 'advanced',
  },
  {
    title: 'nav.session',
    href: '/session',
    icon: Video,
    group: 'advanced',
  },
  {
    title: 'nav.realtime',
    href: '/realtime',
    icon: MonitorPlay,
    group: 'advanced',
  },
  {
    title: 'nav.admin',
    href: '/dashboard',
    icon: LayoutDashboard,
    group: 'advanced',
  },
  {
    title: 'nav.webhooks',
    href: '/webhooks',
    icon: Webhook,
    group: 'advanced',
  },
  {
    title: 'nav.embeddings',
    href: '/embeddings',
    icon: Database,
    group: 'advanced',
  },
  {
    title: 'nav.apiExplorer',
    href: '/api-explorer',
    icon: Code,
    group: 'advanced',
  },
  // Settings
  {
    title: 'nav.settings',
    href: '/settings',
    icon: Settings,
    group: 'settings',
  },
];

interface NavGroup {
  id: string;
  label: string | null;
  collapsible?: boolean;
}

const groups: NavGroup[] = [
  { id: 'main', label: null },
  { id: 'core', label: 'nav.groups.coreFeatures' },
  { id: 'analysis', label: 'nav.groups.analysis' },
  { id: 'advanced', label: 'nav.groups.advanced', collapsible: true },
  { id: 'settings', label: null },
];

export function Sidebar() {
  const pathname = usePathname();
  const { t } = useTranslation();
  const {
    sidebarOpen,
    sidebarCollapsed,
    advancedSidebarExpanded,
    toggleSidebar,
    toggleSidebarCollapsed,
    setAdvancedSidebarExpanded,
  } = useAppStore();

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
              const isAdvancedGroup = group.collapsible;
              const isGroupExpanded = !isAdvancedGroup || advancedSidebarExpanded;

              return (
                <div key={group.id} className="space-y-1">
                  {group.label && !isCollapsed && (
                    isAdvancedGroup ? (
                      <button
                        onClick={() => setAdvancedSidebarExpanded(!advancedSidebarExpanded)}
                        className="flex w-full items-center justify-between px-3 py-2 text-xs font-medium uppercase text-muted-foreground hover:text-foreground transition-colors"
                      >
                        <span>{t(group.label)}</span>
                        <ChevronDown
                          className={cn(
                            'h-3 w-3 transition-transform duration-200',
                            advancedSidebarExpanded ? 'rotate-0' : '-rotate-90'
                          )}
                        />
                      </button>
                    ) : (
                      <p className="px-3 py-2 text-xs font-medium uppercase text-muted-foreground">
                        {t(group.label)}
                      </p>
                    )
                  )}
                  <AnimatePresence initial={false}>
                    {isGroupExpanded && (
                      <motion.div
                        initial={isAdvancedGroup ? { height: 0, opacity: 0 } : false}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={isAdvancedGroup ? { height: 0, opacity: 0 } : undefined}
                        transition={{ duration: 0.2 }}
                        className={isAdvancedGroup ? 'overflow-hidden' : undefined}
                      >
                        {groupItems.map((item) => {
                          const isActive = pathname === item.href;
                          const isHighlighted = 'highlighted' in item && item.highlighted;
                          return (
                            <Link
                              key={item.href}
                              href={item.href}
                              className={cn(
                                'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors mb-0.5',
                                isActive
                                  ? 'bg-primary text-primary-foreground'
                                  : isHighlighted
                                    ? 'bg-gradient-to-r from-blue-500/10 to-purple-500/10 border border-blue-500/20 text-blue-600 dark:text-blue-400 hover:from-blue-500/20 hover:to-purple-500/20'
                                    : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                                isCollapsed && 'justify-center px-2'
                              )}
                              title={isCollapsed ? t(item.title) : undefined}
                            >
                              <item.icon className={cn(
                                'h-4 w-4 shrink-0',
                                isHighlighted && !isActive && 'text-blue-500'
                              )} />
                              {!isCollapsed && (
                                <span className="truncate">{t(item.title)}</span>
                              )}
                            </Link>
                          );
                        })}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              );
            })}
          </nav>
        </ScrollArea>
      </motion.aside>
    </>
  );
}

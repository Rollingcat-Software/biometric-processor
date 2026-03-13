'use client';

import { useTheme } from 'next-themes';
import { Sun, Moon, Globe, Menu, CheckCircle2, AlertCircle, Server } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useTranslation } from 'react-i18next';
import { useAppStore } from '@/lib/store/app-store';
import { useApiHealth } from '@/hooks/use-api-health';

export function Header() {
  const { setTheme } = useTheme();
  const { i18n, t } = useTranslation();
  const toggleSidebar = useAppStore((state) => state.toggleSidebar);
  const { isHealthy, isLoading } = useApiHealth();

  const changeLanguage = (lng: string) => {
    i18n.changeLanguage(lng);
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex h-14 items-center px-4 gap-4">
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden"
          onClick={toggleSidebar}
          aria-label="Toggle sidebar"
        >
          <Menu className="h-5 w-5" />
        </Button>

        {/* Branding */}
        <span className="text-sm font-semibold tracking-tight text-foreground hidden sm:inline-block">
          FIVUCSAS
        </span>

        <div className="flex-1" />

        <div className="flex items-center gap-2">
          {/* API Health Badge */}
          <Badge
            variant={isHealthy ? 'outline' : 'destructive'}
            className="flex items-center gap-1 text-xs"
          >
            {isLoading ? (
              <>
                <Server className="h-3 w-3 animate-pulse" />
                <span className="hidden sm:inline">API...</span>
              </>
            ) : isHealthy ? (
              <>
                <CheckCircle2 className="h-3 w-3 text-green-500" />
                <span className="hidden sm:inline">API</span>
              </>
            ) : (
              <>
                <AlertCircle className="h-3 w-3" />
                <span className="hidden sm:inline">Offline</span>
              </>
            )}
          </Badge>

          {/* Language Switcher */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" aria-label="Change language">
                <Globe className="h-5 w-5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => changeLanguage('en')}>
                English
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => changeLanguage('tr')}>
                Türkçe
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          {/* Theme Switcher */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" aria-label="Toggle theme">
                <Sun className="h-5 w-5 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
                <Moon className="absolute h-5 w-5 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => setTheme('light')}>
                {t('settings.themes.light')}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setTheme('dark')}>
                {t('settings.themes.dark')}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setTheme('system')}>
                {t('settings.themes.system')}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
}

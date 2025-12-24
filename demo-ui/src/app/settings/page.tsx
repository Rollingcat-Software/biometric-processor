'use client';

import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { motion } from 'framer-motion';
import { Settings, Palette, Camera, Server, Bell } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useTheme } from 'next-themes';
import { useAppStore } from '@/lib/store/app-store';
import { toast } from 'sonner';

export default function SettingsPage() {
  const { t, i18n } = useTranslation();
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // Prevent hydration mismatch by only rendering theme-dependent content after mount
  useEffect(() => {
    setMounted(true);
  }, []);
  const {
    apiUrl,
    setApiUrl,
    cameraFacingMode,
    setCameraFacingMode,
    cameraResolution,
    setCameraResolution,
    features,
    setFeatureEnabled,
  } = useAppStore();

  const handleSaveApiUrl = () => {
    toast.success('Settings Saved', {
      description: 'API URL has been updated',
    });
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gray-500/10">
            <Settings className="h-5 w-5 text-gray-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">{t('settings.title')}</h1>
            <p className="text-muted-foreground">Configure application preferences</p>
          </div>
        </div>
      </motion.div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Appearance */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, delay: 0.1 }}
        >
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Palette className="h-5 w-5 text-muted-foreground" />
                <CardTitle>Appearance</CardTitle>
              </div>
              <CardDescription>Customize the look and feel</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Theme */}
              <div className="space-y-2">
                <Label>{t('settings.theme')}</Label>
                {mounted ? (
                  <Select value={theme} onValueChange={setTheme}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="light">{t('settings.themes.light')}</SelectItem>
                      <SelectItem value="dark">{t('settings.themes.dark')}</SelectItem>
                      <SelectItem value="system">{t('settings.themes.system')}</SelectItem>
                    </SelectContent>
                  </Select>
                ) : (
                  <div className="h-10 w-full rounded-md border bg-muted animate-pulse" />
                )}
              </div>

              {/* Language */}
              <div className="space-y-2">
                <Label>{t('settings.language')}</Label>
                <Select value={i18n.language} onValueChange={(v) => i18n.changeLanguage(v)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="en">English</SelectItem>
                    <SelectItem value="tr">Türkçe</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* API Configuration */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, delay: 0.2 }}
        >
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Server className="h-5 w-5 text-muted-foreground" />
                <CardTitle>{t('settings.api.title')}</CardTitle>
              </div>
              <CardDescription>Configure API connection</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <Label>{t('settings.api.url')}</Label>
                <div className="flex gap-2">
                  <Input
                    value={apiUrl}
                    onChange={(e) => setApiUrl(e.target.value)}
                    placeholder="http://localhost:8000"
                  />
                  <Button onClick={handleSaveApiUrl}>Save</Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Camera Settings */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, delay: 0.3 }}
        >
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Camera className="h-5 w-5 text-muted-foreground" />
                <CardTitle>{t('settings.camera.title')}</CardTitle>
              </div>
              <CardDescription>Configure camera preferences</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Facing Mode */}
              <div className="space-y-2">
                <Label>{t('settings.camera.facingMode')}</Label>
                <Select
                  value={cameraFacingMode}
                  onValueChange={(v) => setCameraFacingMode(v as 'user' | 'environment')}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="user">{t('settings.camera.front')}</SelectItem>
                    <SelectItem value="environment">{t('settings.camera.back')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Resolution */}
              <div className="space-y-2">
                <Label>{t('settings.camera.resolution')}</Label>
                <Select
                  value={cameraResolution}
                  onValueChange={(v) => setCameraResolution(v as 'hd' | 'fhd' | '4k')}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="hd">720p (HD)</SelectItem>
                    <SelectItem value="fhd">1080p (Full HD)</SelectItem>
                    <SelectItem value="4k">4K (Ultra HD)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Feature Flags */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, delay: 0.4 }}
        >
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Bell className="h-5 w-5 text-muted-foreground" />
                <CardTitle>Features</CardTitle>
              </div>
              <CardDescription>Enable or disable features</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <Label>Proctoring</Label>
                  <p className="text-sm text-muted-foreground">
                    Real-time exam monitoring
                  </p>
                </div>
                <Switch
                  checked={features.proctoring}
                  onCheckedChange={(v) => setFeatureEnabled('proctoring', v)}
                />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <Label>Batch Processing</Label>
                  <p className="text-sm text-muted-foreground">
                    Process multiple images
                  </p>
                </div>
                <Switch
                  checked={features.batchProcessing}
                  onCheckedChange={(v) => setFeatureEnabled('batchProcessing', v)}
                />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <Label>Webhooks</Label>
                  <p className="text-sm text-muted-foreground">
                    Event notifications
                  </p>
                </div>
                <Switch
                  checked={features.webhooks}
                  onCheckedChange={(v) => setFeatureEnabled('webhooks', v)}
                />
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}

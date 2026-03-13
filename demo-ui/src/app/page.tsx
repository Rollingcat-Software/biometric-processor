'use client';

import { motion } from 'framer-motion';
import Link from 'next/link';
import {
  UserPlus,
  ShieldCheck,
  Search,
  ScanFace,
  ArrowRight,
  Server,
  CheckCircle2,
  AlertCircle,
  Sparkles,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useApiHealth } from '@/hooks/use-api-health';

const capabilities = [
  {
    title: 'Face Enrollment',
    description: 'Register new faces with quality validation and embedding extraction',
    icon: UserPlus,
    href: '/enrollment',
    color: 'text-blue-500',
    bgColor: 'bg-blue-500/10',
  },
  {
    title: '1:1 Verification',
    description: 'Compare two faces for identity verification',
    icon: ShieldCheck,
    href: '/verification',
    color: 'text-green-500',
    bgColor: 'bg-green-500/10',
  },
  {
    title: 'Liveness Detection',
    description: 'Detect presentation attacks and spoofing attempts',
    icon: ScanFace,
    href: '/liveness',
    color: 'text-orange-500',
    bgColor: 'bg-orange-500/10',
  },
  {
    title: '1:N Search',
    description: 'Search for a face across enrolled database',
    icon: Search,
    href: '/search',
    color: 'text-purple-500',
    bgColor: 'bg-purple-500/10',
  },
];

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.3,
    },
  },
};

export default function DashboardPage() {
  const { isHealthy, isLoading, data: healthData } = useApiHealth();

  return (
    <div className="space-y-10">
      {/* Hero Section */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="text-center space-y-6 py-8"
      >
        <h1 className="text-4xl md:text-5xl font-bold tracking-tight bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
          FIVUCSAS Biometric Processor
        </h1>
        <p className="text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto">
          Enterprise-grade facial biometrics platform with enrollment, verification,
          liveness detection, and intelligent face search.
        </p>

        {/* API Health Indicator */}
        <div className="flex justify-center">
          <Badge
            variant={isHealthy ? 'default' : 'destructive'}
            className="flex items-center gap-1.5 px-3 py-1 text-sm"
          >
            {isLoading ? (
              <>
                <Server className="h-3.5 w-3.5 animate-pulse" />
                Checking API...
              </>
            ) : isHealthy ? (
              <>
                <CheckCircle2 className="h-3.5 w-3.5" />
                API Connected
                {healthData?.latency && (
                  <span className="text-xs opacity-75">({healthData.latency}ms)</span>
                )}
              </>
            ) : (
              <>
                <AlertCircle className="h-3.5 w-3.5" />
                API Unavailable
              </>
            )}
          </Badge>
        </div>

        {/* CTA Button */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.3, duration: 0.4 }}
        >
          <Button
            size="lg"
            asChild
            className="gap-2 px-8 py-6 text-lg bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 shadow-lg"
          >
            <Link href="/demo">
              <Sparkles className="h-5 w-5" />
              Start Interactive Demo
              <ArrowRight className="h-5 w-5" />
            </Link>
          </Button>
        </motion.div>
      </motion.div>

      {/* Capability Cards */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-foreground text-center">
          Core Capabilities
        </h2>
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"
        >
          {capabilities.map((capability) => (
            <motion.div key={capability.title} variants={itemVariants}>
              <Link href={capability.href}>
                <Card className="card-hover group h-full cursor-pointer">
                  <CardHeader className="pb-3">
                    <div className="flex items-center gap-3">
                      <div
                        className={`flex h-10 w-10 items-center justify-center rounded-lg ${capability.bgColor}`}
                      >
                        <capability.icon className={`h-5 w-5 ${capability.color}`} />
                      </div>
                      <div className="flex-1">
                        <CardTitle className="text-base">
                          {capability.title}
                        </CardTitle>
                      </div>
                      <ArrowRight className="h-4 w-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
                    </div>
                  </CardHeader>
                  <CardContent className="pt-0">
                    <CardDescription>{capability.description}</CardDescription>
                  </CardContent>
                </Card>
              </Link>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </div>
  );
}

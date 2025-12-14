'use client';

import { motion } from 'framer-motion';
import Link from 'next/link';
import {
  UserPlus,
  ShieldCheck,
  Search,
  ScanFace,
  Activity,
  Users,
  Eye,
  Grid3X3,
  Video,
  Settings,
  ArrowRight,
  Server,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useApiHealth } from '@/hooks/use-api-health';

const features = [
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
    title: '1:N Search',
    description: 'Search for a face across enrolled database',
    icon: Search,
    href: '/search',
    color: 'text-purple-500',
    bgColor: 'bg-purple-500/10',
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
    title: 'Quality Analysis',
    description: 'Analyze face image quality metrics',
    icon: Activity,
    href: '/quality',
    color: 'text-cyan-500',
    bgColor: 'bg-cyan-500/10',
  },
  {
    title: 'Demographics',
    description: 'Estimate age, gender, and emotions',
    icon: Users,
    href: '/demographics',
    color: 'text-pink-500',
    bgColor: 'bg-pink-500/10',
  },
  {
    title: 'Facial Landmarks',
    description: 'View 468-point facial landmark detection',
    icon: Eye,
    href: '/landmarks',
    color: 'text-indigo-500',
    bgColor: 'bg-indigo-500/10',
  },
  {
    title: 'Batch Processing',
    description: 'Process multiple images efficiently',
    icon: Grid3X3,
    href: '/batch',
    color: 'text-yellow-500',
    bgColor: 'bg-yellow-500/10',
  },
  {
    title: 'Real-time Proctoring',
    description: 'Continuous face monitoring with WebSocket streaming',
    icon: Video,
    href: '/session',
    color: 'text-red-500',
    bgColor: 'bg-red-500/10',
  },
];

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.05,
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
  const { isHealthy, isLoading, error, data: healthData } = useApiHealth();

  return (
    <div className="space-y-8">
      {/* Hero Section */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="space-y-4"
      >
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-display-sm font-bold tracking-tight text-foreground">
              Biometric Processor Demo
            </h1>
            <p className="mt-2 text-lg text-muted-foreground">
              Enterprise-grade facial biometrics solution demonstration
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Badge
              variant={isHealthy ? 'default' : 'destructive'}
              className="flex items-center gap-1"
            >
              {isLoading ? (
                <>
                  <Server className="h-3 w-3 animate-pulse" />
                  Checking API...
                </>
              ) : isHealthy ? (
                <>
                  <CheckCircle2 className="h-3 w-3" />
                  API Connected
                </>
              ) : (
                <>
                  <AlertCircle className="h-3 w-3" />
                  API Unavailable
                </>
              )}
            </Badge>
          </div>
        </div>
      </motion.div>

      {/* Quick Stats */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.2, duration: 0.5 }}
        className="grid gap-4 md:grid-cols-4"
      >
        {[
          { label: 'API Version', value: healthData?.version || '1.0.0' },
          { label: 'Status', value: isHealthy ? 'Operational' : 'Offline' },
          { label: 'Features', value: '9 Available' },
          { label: 'Response Time', value: healthData?.latency ? `${healthData.latency}ms` : '-' },
        ].map((stat, index) => (
          <Card key={stat.label}>
            <CardContent className="p-4">
              <div className="text-sm font-medium text-muted-foreground">
                {stat.label}
              </div>
              <div className="mt-1 text-2xl font-semibold">{stat.value}</div>
            </CardContent>
          </Card>
        ))}
      </motion.div>

      {/* Feature Grid */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-foreground">
          Available Features
        </h2>
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
        >
          {features.map((feature) => (
            <motion.div key={feature.title} variants={itemVariants}>
              <Link href={feature.href}>
                <Card className="card-hover group h-full cursor-pointer">
                  <CardHeader className="pb-3">
                    <div className="flex items-center gap-3">
                      <div
                        className={`flex h-10 w-10 items-center justify-center rounded-lg ${feature.bgColor}`}
                      >
                        <feature.icon className={`h-5 w-5 ${feature.color}`} />
                      </div>
                      <div className="flex-1">
                        <CardTitle className="text-base">
                          {feature.title}
                        </CardTitle>
                      </div>
                      <ArrowRight className="h-4 w-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
                    </div>
                  </CardHeader>
                  <CardContent className="pt-0">
                    <CardDescription>{feature.description}</CardDescription>
                  </CardContent>
                </Card>
              </Link>
            </motion.div>
          ))}
        </motion.div>
      </div>

      {/* Admin Quick Links */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.4, duration: 0.5 }}
        className="space-y-4"
      >
        <h2 className="text-lg font-semibold text-foreground">
          Administration
        </h2>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" asChild>
            <Link href="/dashboard">
              <Activity className="mr-2 h-4 w-4" />
              Admin Dashboard
            </Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href="/webhooks">
              <Server className="mr-2 h-4 w-4" />
              Webhooks
            </Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href="/api-explorer">
              <Search className="mr-2 h-4 w-4" />
              API Explorer
            </Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href="/settings">
              <Settings className="mr-2 h-4 w-4" />
              Settings
            </Link>
          </Button>
        </div>
      </motion.div>
    </div>
  );
}

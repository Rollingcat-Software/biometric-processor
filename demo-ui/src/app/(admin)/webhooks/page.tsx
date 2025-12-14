'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  Webhook,
  Plus,
  Trash2,
  Play,
  Clock,
  Link,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { useWebhooks, useCreateWebhook, useDeleteWebhook, useTestWebhook } from '@/hooks/use-webhooks';
import { toast } from 'sonner';

const eventTypes = [
  'enrollment.created',
  'enrollment.deleted',
  'verification.success',
  'verification.failed',
  'liveness.success',
  'liveness.failed',
  'proctoring.incident',
  'proctoring.session_ended',
];

export default function WebhooksPage() {
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [newWebhook, setNewWebhook] = useState({
    url: '',
    secret: '',
    events: [] as string[],
  });

  const { data: webhooks, isLoading } = useWebhooks();
  const createWebhook = useCreateWebhook();
  const deleteWebhook = useDeleteWebhook();
  const testWebhook = useTestWebhook();

  const handleCreate = async () => {
    if (!newWebhook.url || newWebhook.events.length === 0) {
      toast.error('Error', { description: 'URL and at least one event are required' });
      return;
    }

    try {
      await createWebhook.mutateAsync(newWebhook);
      toast.success('Webhook Created', { description: 'Webhook registered successfully' });
      setIsDialogOpen(false);
      setNewWebhook({ url: '', secret: '', events: [] });
    } catch (err: any) {
      toast.error('Error', { description: err.message });
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteWebhook.mutateAsync(id);
      toast.success('Webhook Deleted');
    } catch (err: any) {
      toast.error('Error', { description: err.message });
    }
  };

  const handleTest = async (id: string) => {
    try {
      const result = await testWebhook.mutateAsync(id);
      if (result.success) {
        toast.success('Test Successful', {
          description: `Response time: ${result.response_time_ms}ms`,
        });
      } else {
        toast.error('Test Failed', {
          description: 'Webhook endpoint did not respond correctly',
        });
      }
    } catch (err: any) {
      toast.error('Error', { description: err.message });
    }
  };

  const toggleEvent = (event: string) => {
    setNewWebhook((prev) => ({
      ...prev,
      events: prev.events.includes(event)
        ? prev.events.filter((e) => e !== event)
        : [...prev.events, event],
    }));
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-teal-500/10">
              <Webhook className="h-5 w-5 text-teal-500" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">Webhooks</h1>
              <p className="text-muted-foreground">Manage webhook endpoints for event notifications</p>
            </div>
          </div>

          <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                Add Webhook
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-md">
              <DialogHeader>
                <DialogTitle>Register Webhook</DialogTitle>
                <DialogDescription>
                  Add a new webhook endpoint to receive event notifications
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="url">Endpoint URL</Label>
                  <Input
                    id="url"
                    value={newWebhook.url}
                    onChange={(e) => setNewWebhook((prev) => ({ ...prev, url: e.target.value }))}
                    placeholder="https://your-server.com/webhook"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="secret">Secret (optional)</Label>
                  <Input
                    id="secret"
                    type="password"
                    value={newWebhook.secret}
                    onChange={(e) => setNewWebhook((prev) => ({ ...prev, secret: e.target.value }))}
                    placeholder="Webhook signing secret"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Events</Label>
                  <div className="grid grid-cols-2 gap-2">
                    {eventTypes.map((event) => (
                      <div key={event} className="flex items-center space-x-2">
                        <Switch
                          id={event}
                          checked={newWebhook.events.includes(event)}
                          onCheckedChange={() => toggleEvent(event)}
                        />
                        <Label htmlFor={event} className="text-xs">
                          {event}
                        </Label>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setIsDialogOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={handleCreate} disabled={createWebhook.isPending}>
                  {createWebhook.isPending ? 'Creating...' : 'Create'}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </motion.div>

      {/* Webhooks List */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.1 }}
      >
        <Card>
          <CardHeader>
            <CardTitle>Registered Webhooks</CardTitle>
            <CardDescription>
              {webhooks?.webhooks?.length || 0} webhook{webhooks?.webhooks?.length !== 1 ? 's' : ''} configured
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-20 rounded-lg border animate-pulse bg-muted" />
                ))}
              </div>
            ) : webhooks && webhooks.webhooks && webhooks.webhooks.length > 0 ? (
              <div className="space-y-3">
                {webhooks.webhooks.map((webhook: any) => (
                  <div
                    key={webhook.id}
                    className="flex items-center justify-between rounded-lg border p-4"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <Link className="h-4 w-4 text-muted-foreground" />
                        <span className="font-medium">{webhook.url}</span>
                        <Badge variant={webhook.is_active ? 'default' : 'secondary'}>
                          {webhook.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {webhook.events.map((event: string) => (
                          <Badge key={event} variant="outline" className="text-xs">
                            {event}
                          </Badge>
                        ))}
                      </div>
                      <div className="flex items-center gap-4 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          Created: {new Date(webhook.created_at).toLocaleDateString()}
                        </span>
                        {webhook.last_triggered_at && (
                          <span>
                            Last triggered: {new Date(webhook.last_triggered_at).toLocaleString()}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleTest(webhook.id)}
                        disabled={testWebhook.isPending}
                      >
                        <Play className="mr-1 h-3 w-3" />
                        Test
                      </Button>
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => handleDelete(webhook.id)}
                        disabled={deleteWebhook.isPending}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <Webhook className="h-12 w-12 mb-4" />
                <p>No webhooks configured</p>
                <p className="text-sm">Click &quot;Add Webhook&quot; to register an endpoint</p>
              </div>
            )}
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}

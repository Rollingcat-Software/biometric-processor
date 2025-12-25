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
  Edit,
  AlertTriangle,
  Info,
  Key,
  CheckCircle2,
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
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { useWebhooks, useCreateWebhook, useDeleteWebhook, useTestWebhook, useUpdateWebhook } from '@/hooks/use-webhooks';
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
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [editingWebhook, setEditingWebhook] = useState<any>(null);
  const [newWebhook, setNewWebhook] = useState({
    url: '',
    secret: '',
    events: [] as string[],
  });

  const { data: webhooks, isLoading } = useWebhooks();
  const createWebhook = useCreateWebhook();
  const updateWebhook = useUpdateWebhook();
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
      setIsCreateDialogOpen(false);
      setNewWebhook({ url: '', secret: '', events: [] });
    } catch (err: any) {
      toast.error('Error', { description: err.message });
    }
  };

  const handleEdit = async () => {
    if (!editingWebhook) return;

    try {
      await updateWebhook.mutateAsync({
        id: editingWebhook.id,
        url: editingWebhook.url,
        events: editingWebhook.events,
        secret: editingWebhook.secret,
      });
      toast.success('Webhook Updated', { description: 'Webhook updated successfully' });
      setIsEditDialogOpen(false);
      setEditingWebhook(null);
    } catch (err: any) {
      toast.error('Error', { description: err.message });
    }
  };

  const handleToggleActive = async (webhook: any) => {
    try {
      await updateWebhook.mutateAsync({
        id: webhook.id,
        is_active: !webhook.is_active,
      });
      toast.success(
        webhook.is_active ? 'Webhook Deactivated' : 'Webhook Activated'
      );
    } catch (err: any) {
      toast.error('Error', { description: err.message });
    }
  };

  const openEditDialog = (webhook: any) => {
    setEditingWebhook({ ...webhook });
    setIsEditDialogOpen(true);
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

  const toggleEvent = (event: string, isEditing = false) => {
    if (isEditing && editingWebhook) {
      setEditingWebhook((prev: any) => ({
        ...prev,
        events: prev.events.includes(event)
          ? prev.events.filter((e: string) => e !== event)
          : [...prev.events, event],
      }));
    } else {
      setNewWebhook((prev) => ({
        ...prev,
        events: prev.events.includes(event)
          ? prev.events.filter((e) => e !== event)
          : [...prev.events, event],
      }));
    }
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

          <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
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
                <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
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

      {/* Webhook Setup Documentation */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.05 }}
      >
        <Card className="border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-950/50">
          <CardContent className="pt-6">
            <Accordion type="single" collapsible>
              <AccordionItem value="docs">
                <AccordionTrigger className="hover:no-underline">
                  <div className="flex items-center gap-2">
                    <Info className="h-4 w-4 text-blue-600" />
                    <span className="font-medium text-blue-900 dark:text-blue-100">
                      Webhook Signature Verification Setup
                    </span>
                  </div>
                </AccordionTrigger>
                <AccordionContent>
                  <div className="space-y-4 text-sm text-blue-900 dark:text-blue-100">
                    <div>
                      <h4 className="font-medium mb-2 flex items-center gap-2">
                        <Key className="h-4 w-4" />
                        Verifying Webhook Signatures
                      </h4>
                      <p className="mb-3 text-blue-800 dark:text-blue-200">
                        All webhook requests include an <code className="bg-blue-200 dark:bg-blue-900 px-1 rounded">X-Webhook-Signature</code> header for request verification.
                      </p>
                      <div className="bg-blue-100 dark:bg-blue-900/50 p-3 rounded font-mono text-xs overflow-x-auto">
                        <div className="text-blue-700 dark:text-blue-300"># Python Example</div>
                        <div className="mt-2">import hmac</div>
                        <div>import hashlib</div>
                        <div className="mt-2">def verify_webhook(payload, signature, secret):</div>
                        <div>&nbsp;&nbsp;&nbsp;&nbsp;expected = hmac.new(</div>
                        <div>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;secret.encode(),</div>
                        <div>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;payload.encode(),</div>
                        <div>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;hashlib.sha256</div>
                        <div>&nbsp;&nbsp;&nbsp;&nbsp;).hexdigest()</div>
                        <div>&nbsp;&nbsp;&nbsp;&nbsp;return hmac.compare_digest(expected, signature)</div>
                      </div>
                    </div>
                    <div>
                      <h4 className="font-medium mb-2">Request Headers</h4>
                      <ul className="list-disc list-inside space-y-1 text-blue-800 dark:text-blue-200">
                        <li><code className="bg-blue-200 dark:bg-blue-900 px-1 rounded">X-Webhook-Signature</code> - HMAC SHA256 signature</li>
                        <li><code className="bg-blue-200 dark:bg-blue-900 px-1 rounded">X-Event-Type</code> - Event type that triggered the webhook</li>
                        <li><code className="bg-blue-200 dark:bg-blue-900 px-1 rounded">X-Request-ID</code> - Unique request correlation ID</li>
                        <li><code className="bg-blue-200 dark:bg-blue-900 px-1 rounded">Content-Type</code> - application/json</li>
                      </ul>
                    </div>
                    <div>
                      <h4 className="font-medium mb-2">Best Practices</h4>
                      <ul className="list-disc list-inside space-y-1 text-blue-800 dark:text-blue-200">
                        <li>Always verify signatures before processing webhook data</li>
                        <li>Return 200 OK within 5 seconds to avoid retries</li>
                        <li>Use HTTPS endpoints only in production</li>
                        <li>Implement idempotency to handle duplicate deliveries</li>
                        <li>Store webhook secrets securely (use environment variables)</li>
                      </ul>
                    </div>
                  </div>
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </CardContent>
        </Card>
      </motion.div>

      {/* Edit Webhook Dialog */}
      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Edit Webhook</DialogTitle>
            <DialogDescription>
              Update webhook endpoint configuration
            </DialogDescription>
          </DialogHeader>
          {editingWebhook && (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="edit-url">Endpoint URL</Label>
                <Input
                  id="edit-url"
                  value={editingWebhook.url}
                  onChange={(e) => setEditingWebhook({ ...editingWebhook, url: e.target.value })}
                  placeholder="https://your-server.com/webhook"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-secret">Secret (optional)</Label>
                <Input
                  id="edit-secret"
                  type="password"
                  value={editingWebhook.secret || ''}
                  onChange={(e) => setEditingWebhook({ ...editingWebhook, secret: e.target.value })}
                  placeholder="Webhook signing secret"
                />
              </div>
              <div className="space-y-2">
                <Label>Events</Label>
                <div className="grid grid-cols-2 gap-2">
                  {eventTypes.map((event) => (
                    <div key={event} className="flex items-center space-x-2">
                      <Switch
                        id={`edit-${event}`}
                        checked={editingWebhook.events.includes(event)}
                        onCheckedChange={() => toggleEvent(event, true)}
                      />
                      <Label htmlFor={`edit-${event}`} className="text-xs">
                        {event}
                      </Label>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsEditDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleEdit} disabled={updateWebhook.isPending}>
              {updateWebhook.isPending ? 'Updating...' : 'Update'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

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
                    className="rounded-lg border p-4 space-y-3"
                  >
                    {/* Header Row */}
                    <div className="flex items-start justify-between">
                      <div className="flex-1 space-y-2">
                        <div className="flex items-center gap-2">
                          <Link className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                          <span className="font-medium break-all">{webhook.url}</span>
                        </div>

                        {/* Status Badges */}
                        <div className="flex flex-wrap gap-2 items-center">
                          <Badge variant={webhook.is_active ? 'default' : 'secondary'}>
                            {webhook.is_active ? (
                              <>
                                <CheckCircle2 className="h-3 w-3 mr-1" />
                                Active
                              </>
                            ) : (
                              'Inactive'
                            )}
                          </Badge>

                          {webhook.failure_count > 0 && (
                            <Badge variant="destructive" className="flex items-center gap-1">
                              <AlertTriangle className="h-3 w-3" />
                              {webhook.failure_count} {webhook.failure_count === 1 ? 'failure' : 'failures'}
                            </Badge>
                          )}

                          {webhook.secret && (
                            <Badge variant="outline" className="flex items-center gap-1">
                              <Key className="h-3 w-3" />
                              Signed
                            </Badge>
                          )}
                        </div>
                      </div>

                      {/* Action Buttons */}
                      <div className="flex gap-2 ml-4">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleToggleActive(webhook)}
                          disabled={updateWebhook.isPending}
                          title={webhook.is_active ? 'Deactivate' : 'Activate'}
                        >
                          <Switch checked={webhook.is_active} className="pointer-events-none" />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => openEditDialog(webhook)}
                          disabled={updateWebhook.isPending}
                        >
                          <Edit className="h-3 w-3" />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleTest(webhook.id)}
                          disabled={testWebhook.isPending || !webhook.is_active}
                          title={!webhook.is_active ? 'Activate webhook to test' : 'Test webhook'}
                        >
                          <Play className="h-3 w-3" />
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

                    {/* Events */}
                    <div className="flex flex-wrap gap-1">
                      {webhook.events.map((event: string) => (
                        <Badge key={event} variant="outline" className="text-xs">
                          {event}
                        </Badge>
                      ))}
                    </div>

                    {/* Metadata */}
                    <div className="flex items-center gap-4 text-xs text-muted-foreground border-t pt-2">
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

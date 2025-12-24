'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  Database,
  Search,
  Trash2,
  Download,
  RefreshCw,
  User,
  Calendar,
  Hash,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useEmbeddingList, useDeleteEmbedding } from '@/hooks/use-embeddings';
import { toast } from 'sonner';

interface Embedding {
  id: string;
  user_id: string;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, any>;
}

export default function EmbeddingsPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [selectedEmbedding, setSelectedEmbedding] = useState<Embedding | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [embeddingToDelete, setEmbeddingToDelete] = useState<string | null>(null);

  const { data, isLoading, isError, error, refetch } = useEmbeddingList({
    page,
    page_size: pageSize,
    search: searchQuery || undefined,
  });

  const { mutate: deleteEmbedding, isPending: isDeleting } = useDeleteEmbedding();

  const handleDelete = () => {
    if (!embeddingToDelete) return;

    deleteEmbedding(embeddingToDelete, {
      onSuccess: () => {
        toast.success('Embedding Deleted', {
          description: 'The embedding has been removed from the database',
        });
        setDeleteDialogOpen(false);
        setEmbeddingToDelete(null);
        refetch();
      },
      onError: (err) => {
        toast.error('Delete Failed', { description: err.message });
      },
    });
  };

  const handleExport = async () => {
    try {
      const blob = new Blob([JSON.stringify(data?.embeddings || [], null, 2)], {
        type: 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `embeddings-export-${new Date().toISOString().split('T')[0]}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success('Export Complete', {
        description: `Exported ${data?.embeddings?.length || 0} embeddings`,
      });
    } catch {
      toast.error('Export Failed');
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const totalPages = Math.ceil((data?.total || 0) / pageSize);

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
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-500/10">
              <Database className="h-5 w-5 text-indigo-500" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">Embedding Management</h1>
              <p className="text-muted-foreground">Manage stored face embeddings</p>
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => refetch()}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Refresh
            </Button>
            <Button variant="outline" onClick={handleExport}>
              <Download className="mr-2 h-4 w-4" />
              Export
            </Button>
          </div>
        </div>
      </motion.div>

      {/* Stats Cards */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.1 }}
        className="grid gap-4 md:grid-cols-4"
      >
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-blue-500/10">
                <Database className="h-6 w-6 text-blue-500" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Total Embeddings</p>
                <p className="text-2xl font-bold">{data?.total || 0}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-green-500/10">
                <User className="h-6 w-6 text-green-500" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Unique Users</p>
                <p className="text-2xl font-bold">{data?.unique_users || 0}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-purple-500/10">
                <Calendar className="h-6 w-6 text-purple-500" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Added Today</p>
                <p className="text-2xl font-bold">{data?.added_today || 0}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-orange-500/10">
                <Hash className="h-6 w-6 text-orange-500" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Avg per User</p>
                <p className="text-2xl font-bold">
                  {data?.unique_users ? (data.total / data.unique_users).toFixed(1) : '0'}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Search and Filters */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.2 }}
      >
        <Card>
          <CardHeader>
            <CardTitle>Search & Filter</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-4">
              <div className="flex-1">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    value={searchQuery}
                    onChange={(e) => {
                      setSearchQuery(e.target.value);
                      setPage(1);
                    }}
                    placeholder="Search by user ID..."
                    className="pl-9"
                  />
                </div>
              </div>
              <Select
                value={pageSize.toString()}
                onValueChange={(v) => {
                  setPageSize(parseInt(v));
                  setPage(1);
                }}
              >
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="10">10 per page</SelectItem>
                  <SelectItem value="20">20 per page</SelectItem>
                  <SelectItem value="50">50 per page</SelectItem>
                  <SelectItem value="100">100 per page</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Embeddings Table */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.3 }}
      >
        <Card>
          <CardHeader>
            <CardTitle>Embeddings</CardTitle>
            <CardDescription>
              {data?.total || 0} total embeddings
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex items-center justify-center py-12">
                <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
              </div>
            ) : isError ? (
              <div className="flex items-center justify-center py-12 text-red-600">
                <AlertCircle className="mr-2 h-5 w-5" />
                <span>{error?.message || 'Failed to load embeddings'}</span>
              </div>
            ) : data?.embeddings?.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <Database className="h-12 w-12 mb-4" />
                <p>No embeddings found</p>
              </div>
            ) : (
              <>
                <ScrollArea className="h-[400px]">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left p-3 font-medium">ID</th>
                        <th className="text-left p-3 font-medium">User ID</th>
                        <th className="text-left p-3 font-medium">Created</th>
                        <th className="text-left p-3 font-medium">Updated</th>
                        <th className="text-right p-3 font-medium">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data?.embeddings?.map((embedding: Embedding) => (
                        <tr
                          key={embedding.id}
                          className="border-b hover:bg-muted/50 cursor-pointer"
                          onClick={() => setSelectedEmbedding(embedding)}
                        >
                          <td className="p-3">
                            <code className="text-xs bg-muted px-2 py-1 rounded">
                              {embedding.id.slice(0, 8)}...
                            </code>
                          </td>
                          <td className="p-3">
                            <Badge variant="outline">{embedding.user_id}</Badge>
                          </td>
                          <td className="p-3 text-sm text-muted-foreground">
                            {formatDate(embedding.created_at)}
                          </td>
                          <td className="p-3 text-sm text-muted-foreground">
                            {formatDate(embedding.updated_at)}
                          </td>
                          <td className="p-3 text-right">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-red-600 hover:text-red-700"
                              onClick={(e) => {
                                e.stopPropagation();
                                setEmbeddingToDelete(embedding.id);
                                setDeleteDialogOpen(true);
                              }}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </ScrollArea>

                {/* Pagination */}
                <div className="flex items-center justify-between mt-4 pt-4 border-t">
                  <p className="text-sm text-muted-foreground">
                    Showing {((page - 1) * pageSize) + 1} to {Math.min(page * pageSize, data?.total || 0)} of {data?.total || 0}
                  </p>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page === 1}
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <span className="text-sm">
                      Page {page} of {totalPages || 1}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                      disabled={page >= totalPages}
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </motion.div>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Embedding</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this embedding? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={isDeleting}>
              {isDeleting ? 'Deleting...' : 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Embedding Details Dialog */}
      <Dialog open={!!selectedEmbedding} onOpenChange={() => setSelectedEmbedding(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Embedding Details</DialogTitle>
          </DialogHeader>
          {selectedEmbedding && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label className="text-muted-foreground">ID</Label>
                  <p className="font-mono text-sm">{selectedEmbedding.id}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">User ID</Label>
                  <p className="font-medium">{selectedEmbedding.user_id}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">Created</Label>
                  <p className="text-sm">{formatDate(selectedEmbedding.created_at)}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">Updated</Label>
                  <p className="text-sm">{formatDate(selectedEmbedding.updated_at)}</p>
                </div>
              </div>
              {selectedEmbedding.metadata && (
                <div>
                  <Label className="text-muted-foreground">Metadata</Label>
                  <pre className="mt-2 p-3 bg-muted rounded-lg text-xs overflow-auto max-h-40">
                    {JSON.stringify(selectedEmbedding.metadata, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

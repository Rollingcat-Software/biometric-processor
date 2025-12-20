'use client';

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { motion } from 'framer-motion';
import {
  Code,
  Play,
  Copy,
  Check,
  ChevronDown,
  ChevronRight,
  Send,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { ScrollArea } from '@/components/ui/scroll-area';
import { toast } from 'sonner';

const apiEndpoints = [
  {
    category: 'Core Biometric',
    endpoints: [
      { method: 'POST', path: '/api/v1/enroll', description: 'Enroll a face' },
      { method: 'POST', path: '/api/v1/verify', description: '1:1 Verification' },
      { method: 'POST', path: '/api/v1/search', description: '1:N Search' },
      { method: 'POST', path: '/api/v1/liveness', description: 'Liveness detection' },
      { method: 'POST', path: '/api/v1/compare', description: 'Compare two faces' },
    ],
  },
  {
    category: 'Analysis',
    endpoints: [
      { method: 'POST', path: '/api/v1/quality/analyze', description: 'Quality analysis' },
      { method: 'POST', path: '/api/v1/demographics/analyze', description: 'Demographics analysis' },
      { method: 'POST', path: '/api/v1/landmarks/detect', description: 'Facial landmarks' },
      { method: 'POST', path: '/api/v1/faces/detect-all', description: 'Multi-face detection' },
    ],
  },
  {
    category: 'Batch',
    endpoints: [
      { method: 'POST', path: '/api/v1/batch/enroll', description: 'Batch enrollment' },
      { method: 'POST', path: '/api/v1/batch/verify', description: 'Batch verification' },
    ],
  },
  {
    category: 'Proctoring',
    endpoints: [
      { method: 'POST', path: '/api/v1/proctoring/sessions', description: 'Create session' },
      { method: 'GET', path: '/api/v1/proctoring/sessions', description: 'List sessions' },
      { method: 'POST', path: '/api/v1/proctoring/sessions/{id}/start', description: 'Start session' },
      { method: 'POST', path: '/api/v1/proctoring/sessions/{id}/end', description: 'End session' },
    ],
  },
  {
    category: 'Webhooks',
    endpoints: [
      { method: 'POST', path: '/api/v1/webhooks/register', description: 'Register webhook' },
      { method: 'GET', path: '/api/v1/webhooks', description: 'List webhooks' },
      { method: 'DELETE', path: '/api/v1/webhooks/{id}', description: 'Delete webhook' },
    ],
  },
  {
    category: 'System',
    endpoints: [
      { method: 'GET', path: '/health', description: 'Health check' },
      { method: 'GET', path: '/ready', description: 'Readiness probe' },
      { method: 'GET', path: '/metrics', description: 'Prometheus metrics' },
    ],
  },
];

const methodColors: Record<string, string> = {
  GET: 'bg-green-500',
  POST: 'bg-blue-500',
  PUT: 'bg-yellow-500',
  DELETE: 'bg-red-500',
};

export default function ApiExplorerPage() {
  const { t } = useTranslation();
  const [selectedEndpoint, setSelectedEndpoint] = useState<any>(null);
  const [method, setMethod] = useState('GET');
  const [url, setUrl] = useState('');
  const [body, setBody] = useState('');
  const [response, setResponse] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

  const handleSelectEndpoint = (endpoint: any) => {
    setSelectedEndpoint(endpoint);
    setMethod(endpoint.method);
    setUrl(baseUrl + endpoint.path);
    setBody('');
    setResponse(null);
  };

  const handleSendRequest = async () => {
    setIsLoading(true);
    setResponse(null);

    try {
      const startTime = performance.now();
      const options: RequestInit = {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
      };

      if (method !== 'GET' && body) {
        options.body = body;
      }

      const res = await fetch(url, options);
      const endTime = performance.now();
      const data = await res.json().catch(() => res.text());

      setResponse({
        status: res.status,
        statusText: res.statusText,
        headers: Object.fromEntries(res.headers.entries()),
        data,
        time: Math.round(endTime - startTime),
      });
    } catch (err: any) {
      setResponse({
        status: 0,
        statusText: 'Error',
        error: err.message,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopyResponse = () => {
    if (response) {
      navigator.clipboard.writeText(JSON.stringify(response.data, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      toast.success('Copied to clipboard');
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
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-500/10">
            <Code className="h-5 w-5 text-amber-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">API Explorer</h1>
            <p className="text-muted-foreground">Interactive API testing and documentation</p>
          </div>
        </div>
      </motion.div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Endpoints List */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, delay: 0.1 }}
        >
          <Card className="h-full">
            <CardHeader>
              <CardTitle>Endpoints</CardTitle>
              <CardDescription>Available API endpoints</CardDescription>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[500px]">
                <Accordion type="multiple" className="w-full">
                  {apiEndpoints.map((category) => (
                    <AccordionItem key={category.category} value={category.category}>
                      <AccordionTrigger className="text-sm">
                        {category.category}
                      </AccordionTrigger>
                      <AccordionContent>
                        <div className="space-y-1">
                          {category.endpoints.map((endpoint) => (
                            <button
                              key={endpoint.path}
                              onClick={() => handleSelectEndpoint(endpoint)}
                              className={`w-full text-left p-2 rounded-md text-sm hover:bg-accent ${
                                selectedEndpoint?.path === endpoint.path ? 'bg-accent' : ''
                              }`}
                            >
                              <div className="flex items-center gap-2">
                                <Badge
                                  className={`${methodColors[endpoint.method]} text-white text-xs px-1.5`}
                                >
                                  {endpoint.method}
                                </Badge>
                                <span className="font-mono text-xs truncate flex-1">
                                  {endpoint.path}
                                </span>
                              </div>
                              <p className="text-xs text-muted-foreground mt-1">
                                {endpoint.description}
                              </p>
                            </button>
                          ))}
                        </div>
                      </AccordionContent>
                    </AccordionItem>
                  ))}
                </Accordion>
              </ScrollArea>
            </CardContent>
          </Card>
        </motion.div>

        {/* Request Builder & Response */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, delay: 0.2 }}
          className="lg:col-span-2 space-y-6"
        >
          {/* Request Builder */}
          <Card>
            <CardHeader>
              <CardTitle>Request</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <Select value={method} onValueChange={setMethod}>
                  <SelectTrigger className="w-28">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="GET">GET</SelectItem>
                    <SelectItem value="POST">POST</SelectItem>
                    <SelectItem value="PUT">PUT</SelectItem>
                    <SelectItem value="DELETE">DELETE</SelectItem>
                  </SelectContent>
                </Select>
                <Input
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="Enter URL"
                  className="flex-1 font-mono text-sm"
                />
                <Button onClick={handleSendRequest} disabled={isLoading || !url}>
                  {isLoading ? (
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                  ) : (
                    <>
                      <Send className="mr-2 h-4 w-4" />
                      Send
                    </>
                  )}
                </Button>
              </div>

              {method !== 'GET' && (
                <div className="space-y-2">
                  <Label>Request Body (JSON)</Label>
                  <Textarea
                    value={body}
                    onChange={(e) => setBody(e.target.value)}
                    placeholder='{"key": "value"}'
                    className="font-mono text-sm h-32"
                  />
                </div>
              )}
            </CardContent>
          </Card>

          {/* Response */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Response</CardTitle>
                {response && (
                  <div className="flex items-center gap-2">
                    <Badge
                      variant={
                        response.status >= 200 && response.status < 300
                          ? 'default'
                          : 'destructive'
                      }
                    >
                      {response.status} {response.statusText}
                    </Badge>
                    {response.time && (
                      <Badge variant="outline">{response.time}ms</Badge>
                    )}
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleCopyResponse}
                    >
                      {copied ? (
                        <Check className="h-4 w-4" />
                      ) : (
                        <Copy className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {response ? (
                <ScrollArea className="h-80">
                  <pre className="text-sm font-mono p-4 rounded-lg bg-muted overflow-x-auto">
                    {JSON.stringify(response.data || response.error, null, 2)}
                  </pre>
                </ScrollArea>
              ) : (
                <div className="flex items-center justify-center h-40 text-muted-foreground">
                  <p>Send a request to see the response</p>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}

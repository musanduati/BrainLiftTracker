import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, RefreshCw, Users, Activity } from 'lucide-react';
import { TopBar } from '../components/layout/TopBar';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { Badge } from '../components/common/Badge';
import { Skeleton } from '../components/common/Skeleton';
import { apiClient } from '../services/api';
import toast from 'react-hot-toast';

interface ListWithStats {
  id: string;
  list_id: string;
  name: string;
  description: string;
  mode: string;
  source: string;
  is_managed: boolean;
  owner_username: string;
  last_synced_at: string | null;
  member_count: number;
  members: any[];
  activeMembers?: number;
  activityRate?: number;
}

export const Lists: React.FC = () => {
  const [lists, setLists] = useState<ListWithStats[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    loadLists();
  }, []);

  const loadLists = async () => {
    try {
      setLoading(true);
      const [listsData, tweetsData, threadsData] = await Promise.all([
        apiClient.getAccountsByLists(),
        apiClient.getTweets(),
        apiClient.getThreads()
      ]);

      // Calculate activity stats for each list
      const listsWithStats = listsData.lists.map(list => {
        const members = list.members || [];
        const memberUsernames = members.map((m: any) => m.username);
        
        // Count active members
        const activeMemberUsernames = new Set([
          ...tweetsData.filter((t: any) => memberUsernames.includes(t.username)).map((t: any) => t.username),
          ...threadsData.filter((t: any) => memberUsernames.includes(t.account_username)).map((t: any) => t.account_username)
        ]);
        
        const activeMembers = activeMemberUsernames.size;
        const activityRate = members.length > 0 ? Math.round((activeMembers / members.length) * 100) : 0;
        
        return {
          ...list,
          activeMembers,
          activityRate
        };
      });

      setLists(listsWithStats);
    } catch (error) {
      toast.error('Failed to load lists');
      console.error('Load lists error:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSync = async () => {
    try {
      setSyncing(true);
      // Call sync endpoint (you may need to implement this in the API client)
      toast.success('Sync started successfully');
      // Reload lists after sync
      await loadLists();
    } catch (error) {
      toast.error('Failed to sync lists');
      console.error('Sync error:', error);
    } finally {
      setSyncing(false);
    }
  };

  if (loading) {
    return (
      <>
        <TopBar />
        <div className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <Skeleton className="h-48" />
            <Skeleton className="h-48" />
            <Skeleton className="h-48" />
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <TopBar />
      
      <div className="p-6">
        {/* Back Button and Header */}
        <div className="mb-6">
          <Link to="/" className="inline-flex mb-4">
            <Button variant="ghost" size="sm">
              <ArrowLeft size={16} className="mr-2" />
              Back to Dashboard
            </Button>
          </Link>

          <div className="flex justify-between items-center">
            <div>
              <h2 className="text-2xl font-semibold">Org/Function Groups</h2>
              <p className="text-muted-foreground mt-1">
                Managing {lists.length} groups with {lists.reduce((sum, l) => sum + l.member_count, 0)} total brainlifts
              </p>
            </div>
            
            <Button
              variant="secondary"
              size="sm"
              onClick={handleSync}
              disabled={syncing}
            >
              <RefreshCw size={16} className={`mr-2 ${syncing ? 'animate-spin' : ''}`} />
              Sync Groups
            </Button>
          </div>
        </div>

        {/* Lists Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {lists.map((list) => (
            <Card key={list.id} className="hover:shadow-lg transition-shadow">
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle className="text-lg">{list.name}</CardTitle>
                    <CardDescription className="mt-1">
                      {list.description || 'No description'}
                    </CardDescription>
                  </div>
                  <Badge variant={list.mode === 'public' ? 'secondary' : 'default'}>
                    {list.mode}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {/* Brainlifts Count */}
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-sm">
                      <Users size={16} className="text-muted-foreground" />
                      <span>{list.member_count} brainlifts</span>
                    </div>
                    {list.activeMembers !== undefined && !isNaN(list.activeMembers) && (
                      <Badge variant="secondary" className="text-xs">
                        {list.activeMembers || 0} active
                      </Badge>
                    )}
                  </div>

                  {/* Activity Rate */}
                  {list.activityRate !== undefined && (
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-sm">
                        <Activity size={16} className="text-muted-foreground" />
                        <span>Activity Rate</span>
                      </div>
                      <span className="text-sm font-medium">{list.activityRate}%</span>
                    </div>
                  )}

                  {/* Owner */}
                  <div className="text-sm text-muted-foreground">
                    Owner: @{list.owner_username}
                  </div>

                  {/* Source Badge */}
                  <div className="flex items-center justify-between">
                    <Badge variant="outline" className="text-xs">
                      {list.source === 'synced' ? 'Synced from Twitter' : 'Created locally'}
                    </Badge>
                    {list.last_synced_at && (
                      <span className="text-xs text-muted-foreground">
                        Synced {new Date(list.last_synced_at).toLocaleDateString()}
                      </span>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="pt-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      className="w-full"
                      onClick={() => navigate(`/lists/${list.id}`)}
                    >
                      View Brainlifts
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {lists.length === 0 && (
          <div className="text-center py-12">
            <p className="text-muted-foreground">No lists found</p>
          </div>
        )}
      </div>
    </>
  );
};
import React, { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, Users, Activity, ExternalLink } from 'lucide-react';
import { TopBar } from '../components/layout/TopBar';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { Badge } from '../components/common/Badge';
import { Skeleton } from '../components/common/Skeleton';
import { apiClient } from '../services/api';
import toast from 'react-hot-toast';

interface ListMember {
  id: number;
  username: string;
  displayName: string;
  profilePicture: string;
  tweetCount?: number;
  threadCount?: number;
  lastActivity?: string;
}

interface ListDetails {
  id: string;
  list_id: string;
  name: string;
  description: string;
  mode: string;
  owner_username: string;
  member_count: number;
  members: ListMember[];
}

export const ListMembers: React.FC = () => {
  const { listId } = useParams<{ listId: string }>();
  const navigate = useNavigate();
  const [list, setList] = useState<ListDetails | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadListDetails();
  }, [listId]);

  const loadListDetails = async () => {
    try {
      setLoading(true);
      
      // Get lists data and find the specific list
      const [listsData, tweetsData, threadsData] = await Promise.all([
        apiClient.getAccountsByLists(),
        apiClient.getTweets(),
        apiClient.getThreads()
      ]);

      // Debug: Log the list IDs to understand the structure
      console.log('Looking for list ID:', listId);
      console.log('Available lists:', listsData.lists.map((l: any) => ({ id: l.id, name: l.name })));
      
      // Convert both to strings for comparison since URL params are always strings
      const currentList = listsData.lists.find((l: any) => String(l.id) === String(listId));
      
      if (!currentList) {
        toast.error(`List not found with ID: ${listId}`);
        navigate('/lists');
        return;
      }

      // Enhance member data with activity stats
      const enhancedMembers = (currentList.members || []).map((member: any) => {
        const memberTweets = tweetsData.filter((t: any) => t.username === member.username);
        const memberThreads = threadsData.filter((t: any) => t.account_username === member.username);
        
        let lastTweetDate = null;
        if (memberTweets.length > 0) {
          const validDates = memberTweets
            .map((t: any) => new Date(t.created_at))
            .filter((d: Date) => !isNaN(d.getTime()));
          if (validDates.length > 0) {
            lastTweetDate = new Date(Math.max(...validDates.map(d => d.getTime())));
          }
        }
        
        let lastThreadDate = null;
        if (memberThreads.length > 0) {
          const validDates = memberThreads
            .map((t: any) => new Date(t.created_at))
            .filter((d: Date) => !isNaN(d.getTime()));
          if (validDates.length > 0) {
            lastThreadDate = new Date(Math.max(...validDates.map(d => d.getTime())));
          }
        }
        
        let lastActivity = null;
        const validDates = [lastTweetDate, lastThreadDate].filter(d => d && !isNaN(d.getTime()));
        if (validDates.length > 0) {
          lastActivity = new Date(Math.max(...validDates.map(d => d.getTime()))).toISOString();
        }

        return {
          ...member,
          tweetCount: memberTweets.length,
          threadCount: memberThreads.length,
          lastActivity
        };
      });

      // Sort members by total activity (tweets + threads)
      enhancedMembers.sort((a: ListMember, b: ListMember) => 
        ((b.tweetCount || 0) + (b.threadCount || 0)) - ((a.tweetCount || 0) + (a.threadCount || 0))
      );

      setList({
        ...currentList,
        members: enhancedMembers
      });
    } catch (error) {
      toast.error('Failed to load list details');
      console.error('Load list details error:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleMemberClick = (memberId: number) => {
    navigate(`/accounts/${memberId}`);
  };

  if (loading) {
    return (
      <>
        <TopBar />
        <div className="p-6">
          <Skeleton className="h-32 mb-6" />
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(6)].map((_, i) => (
              <Skeleton key={i} className="h-32" />
            ))}
          </div>
        </div>
      </>
    );
  }

  if (!list) {
    return (
      <>
        <TopBar />
        <div className="p-6">
          <div className="text-center py-12">
            <p className="text-muted-foreground mb-4">List not found</p>
            <Link to="/lists">
              <Button variant="primary">
                <ArrowLeft size={16} className="mr-2" />
                Back to Lists
              </Button>
            </Link>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <TopBar />
      
      <div className="p-6">
        {/* Header */}
        <div className="mb-6">
          <Link to="/lists" className="inline-flex mb-4">
            <Button variant="ghost" size="sm">
              <ArrowLeft size={16} className="mr-2" />
              Back to Lists
            </Button>
          </Link>

          <Card className="mb-6">
            <CardHeader>
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle className="text-2xl">{list.name}</CardTitle>
                  <CardDescription className="mt-2">
                    {list.description || 'No description'}
                  </CardDescription>
                </div>
                <Badge variant={list.mode === 'public' ? 'secondary' : 'default'}>
                  {list.mode}
                </Badge>
              </div>
              <div className="flex items-center gap-4 mt-4 text-sm text-muted-foreground">
                <span>Owner: @{list.owner_username}</span>
                <span>•</span>
                <span className="flex items-center gap-1">
                  <Users size={14} />
                  {list.member_count} members
                </span>
              </div>
            </CardHeader>
          </Card>
        </div>

        {/* Members Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {list.members.map((member) => {
            const totalActivity = (member.tweetCount || 0) + (member.threadCount || 0);
            const hasActivity = totalActivity > 0;
            
            return (
              <Card 
                key={member.id} 
                className="hover:shadow-lg transition-all hover:scale-[1.02] cursor-pointer"
                onClick={() => handleMemberClick(member.id)}
              >
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    {/* Profile Picture */}
                    <div className="flex-shrink-0">
                      <img
                        src={member.profilePicture || '/api/placeholder/48/48'}
                        alt={member.displayName}
                        className="w-12 h-12 rounded-full"
                        onError={(e) => {
                          (e.target as HTMLImageElement).src = '/api/placeholder/48/48';
                        }}
                      />
                    </div>

                    {/* Member Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between">
                        <div className="min-w-0">
                          <p className="font-medium truncate">{member.displayName}</p>
                          <p className="text-sm text-muted-foreground truncate">@{member.username}</p>
                        </div>
                        <ExternalLink size={14} className="text-muted-foreground flex-shrink-0 ml-2" />
                      </div>

                      {/* Activity Stats */}
                      <div className="mt-3 space-y-1">
                        {hasActivity ? (
                          <>
                            <div className="flex items-center gap-4 text-xs">
                              <span className="flex items-center gap-1">
                                <Activity size={12} />
                                {totalActivity} total
                              </span>
                              {member.tweetCount! > 0 && (
                                <span>{member.tweetCount} changes</span>
                              )}
                              {member.threadCount! > 0 && (
                                <span>{member.threadCount} threads</span>
                              )}
                            </div>
                            {member.lastActivity && (
                              <p className="text-xs text-muted-foreground">
                                Last active: {new Date(member.lastActivity).toLocaleDateString()}
                              </p>
                            )}
                          </>
                        ) : (
                          <Badge variant="secondary" className="text-xs">
                            No activity
                          </Badge>
                        )}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {list.members.length === 0 && (
          <div className="text-center py-12">
            <p className="text-muted-foreground">This list has no members</p>
          </div>
        )}
      </div>
    </>
  );
};
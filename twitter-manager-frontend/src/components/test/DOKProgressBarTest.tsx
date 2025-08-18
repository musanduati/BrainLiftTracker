import React from 'react';
import { DOKProgressBar, DOKLegend } from '../common/DOKProgressBar';
// import { Toggle } from '../common/Toggle';
import { DOKBreakdown } from '../../types';
import { Card, CardContent, CardHeader, CardTitle } from '../common/Card';

// Test data mimicking real DOK breakdown from our verified klair_three account
const testDOKData: DOKBreakdown = {
  dok3: {
    added: 10,
    updated: 5,
    deleted: 7,
    total: 17,
    percentage: 62.96
  },
  dok4: {
    added: 7,
    updated: 2,
    deleted: 3,
    total: 10,
    percentage: 37.04
  }
};

const testAccounts = [
  {
    name: 'klair_three (Test Data)',
    totalTweets: 33,
    dokBreakdown: testDOKData
  },
  {
    name: 'Account with DOK3 only',
    totalTweets: 15,
    dokBreakdown: {
      dok3: { added: 10, updated: 2, deleted: 3, total: 13, percentage: 100 },
      dok4: { added: 0, updated: 0, deleted: 0, total: 0, percentage: 0 }
    }
  },
  {
    name: 'Account with DOK4 only',
    totalTweets: 20,
    dokBreakdown: {
      dok3: { added: 0, updated: 0, deleted: 0, total: 0, percentage: 0 },
      dok4: { added: 12, updated: 3, deleted: 5, total: 17, percentage: 100 }
    }
  },
  {
    name: 'Mixed Activity Account',
    totalTweets: 50,
    dokBreakdown: {
      dok3: { added: 8, updated: 2, deleted: 4, total: 12, percentage: 57.14 },
      dok4: { added: 6, updated: 1, deleted: 3, total: 9, percentage: 42.86 }
    }
  },
  {
    name: 'Low Activity Account',
    totalTweets: 5,
    dokBreakdown: {
      dok3: { added: 2, updated: 1, deleted: 1, total: 3, percentage: 100 },
      dok4: { added: 0, updated: 0, deleted: 0, total: 0, percentage: 0 }
    }
  }
];

export const DOKProgressBarTest: React.FC = () => {
  return (
    <div className="p-6 space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            🧪 DOK Progress Bar Test Component
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Legend */}
          <div className="p-4 bg-muted/50 rounded-lg">
            <h3 className="text-sm font-medium mb-3">DOK Activity Legend:</h3>
            <DOKLegend />
          </div>

          {/* Test Progress Bars */}
          <div className="space-y-6">
            {testAccounts.map((account, index) => (
              <div key={index} className="space-y-2">
                <div className="flex justify-between items-center">
                  <h4 className="font-medium">{account.name}</h4>
                  <span className="text-sm text-muted-foreground">
                    {account.totalTweets} total tweets
                  </span>
                </div>
                <DOKProgressBar
                  dokBreakdown={account.dokBreakdown}
                  totalTweets={account.totalTweets}
                  height="md"
                  className="cursor-pointer"
                />
                <div className="text-xs text-muted-foreground pl-2">
                  DOK Changes: {account.dokBreakdown.dok3.total + account.dokBreakdown.dok4.total} | 
                  Regular Posts: {account.totalTweets - (account.dokBreakdown.dok3.total + account.dokBreakdown.dok4.total)} |
                  DOK3: {account.dokBreakdown.dok3.total} |
                  DOK4: {account.dokBreakdown.dok4.total}
                </div>
              </div>
            ))}
          </div>

          {/* Different Heights */}
          <div className="space-y-4">
            <h3 className="font-medium">Different Heights:</h3>
            <div className="space-y-3">
              <div>
                <div className="text-sm text-muted-foreground mb-1">Small (h-4)</div>
                <DOKProgressBar
                  dokBreakdown={testDOKData}
                  totalTweets={33}
                  height="sm"
                />
              </div>
              <div>
                <div className="text-sm text-muted-foreground mb-1">Medium (h-6)</div>
                <DOKProgressBar
                  dokBreakdown={testDOKData}
                  totalTweets={33}
                  height="md"
                />
              </div>
              <div>
                <div className="text-sm text-muted-foreground mb-1">Large (h-8)</div>
                <DOKProgressBar
                  dokBreakdown={testDOKData}
                  totalTweets={33}
                  height="lg"
                />
              </div>
            </div>
          </div>

          {/* Edge Cases */}
          <div className="space-y-4">
            <h3 className="font-medium">Edge Cases:</h3>
            <div className="space-y-3">
              <div>
                <div className="text-sm text-muted-foreground mb-1">No Activity</div>
                <DOKProgressBar
                  dokBreakdown={{
                    dok3: { added: 0, updated: 0, deleted: 0, total: 0, percentage: 0 },
                    dok4: { added: 0, updated: 0, deleted: 0, total: 0, percentage: 0 }
                  }}
                  totalTweets={0}
                  height="md"
                />
              </div>
              <div>
                <div className="text-sm text-muted-foreground mb-1">Only Regular Posts (No DOK)</div>
                <DOKProgressBar
                  dokBreakdown={{
                    dok3: { added: 0, updated: 0, deleted: 0, total: 0, percentage: 0 },
                    dok4: { added: 0, updated: 0, deleted: 0, total: 0, percentage: 0 }
                  }}
                  totalTweets={25}
                  height="md"
                />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
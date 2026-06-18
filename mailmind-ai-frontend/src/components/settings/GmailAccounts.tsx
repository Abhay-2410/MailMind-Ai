import { Mail, RefreshCw } from "lucide-react";



import { GoogleLoginButton } from "@/components/auth/GoogleLoginButton";

import { Badge } from "@/components/ui/badge";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import { useAuth } from "@/hooks/useAuth";

import { formatEmailDate } from "@/lib/format";

import type { SettingsResponse } from "@/types/settings";



interface GmailAccountsProps {

  settings: SettingsResponse;

}



export function GmailAccounts({ settings }: GmailAccountsProps) {

  const { accounts } = settings;

  const { loginWithGoogle } = useAuth();



  return (

    <Card className="surface-card">

      <CardHeader>

        <CardTitle className="flex items-center gap-2 text-lg">

          <Mail className="h-5 w-5 text-brand-green" />

          Gmail accounts

        </CardTitle>

        <CardDescription>Manage connected Gmail accounts used for inbox sync</CardDescription>

      </CardHeader>

      <CardContent className="space-y-4">

        {accounts.length === 0 ? (

          <div className="rounded-xl border border-dashed border-border bg-white/50 p-6 text-center">

            <p className="text-sm text-brand-muted">No Gmail account connected.</p>

            <p className="mt-2 text-sm text-brand-muted">

              Sign in with Google to connect your inbox and enable sync.

            </p>

            <div className="mt-4">

              <GoogleLoginButton onClick={() => void loginWithGoogle()} />

            </div>

          </div>

        ) : (

          <ul className="space-y-3">

            {accounts.map((account) => (

              <li

                key={account.id}

                className="flex flex-col gap-3 rounded-xl border border-border bg-white/70 p-4 sm:flex-row sm:items-center sm:justify-between"

              >

                <div>

                  <div className="flex flex-wrap items-center gap-2">

                    <p className="font-medium text-brand-text">{account.email}</p>

                    {account.is_primary ? (

                      <Badge className="border-0 bg-brand-green-soft text-brand-green">Primary</Badge>

                    ) : null}

                    {!account.is_active ? (

                      <Badge variant="outline" className="text-brand-muted">

                        Inactive

                      </Badge>

                    ) : null}

                  </div>

                  {account.last_synced_at ? (

                    <p className="mt-1 flex items-center gap-1 text-sm text-brand-muted">

                      <RefreshCw className="h-3.5 w-3.5" />

                      Last synced {formatEmailDate(account.last_synced_at)}

                    </p>

                  ) : (

                    <p className="mt-1 text-sm text-brand-muted">Not synced yet</p>

                  )}

                </div>

              </li>

            ))}

          </ul>

        )}

      </CardContent>

    </Card>

  );

}


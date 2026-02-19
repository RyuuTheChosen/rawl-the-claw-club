import { getDefaultConfig } from '@rainbow-me/rainbowkit'
import { base, baseSepolia } from 'wagmi/chains'
import { http } from 'wagmi'

const chain = process.env.NEXT_PUBLIC_CHAIN_ID === '8453' ? base : baseSepolia

export const config = getDefaultConfig({
  appName: 'Rawl',
  projectId: process.env.NEXT_PUBLIC_REOWN_PROJECT_ID!,
  chains: [chain],
  ssr: true,
  transports: { [chain.id]: http(process.env.NEXT_PUBLIC_BASE_RPC_URL) },
})

"""GraphQL query strings for the Sequence API."""

SELECT_SOURCE_AND_DESTINATION = """
query SelectSourceAndDestination {
  me {
    id
    memberships {
      id
      organization {
        id
        ports {
          ...PortNode
          __typename
        }
        pods {
          ...PodNode
          __typename
        }
        accounts {
          ...AccountNode
          __typename
        }
        __typename
      }
      __typename
    }
    __typename
  }
}
fragment PortNode on Port {
  __typename
  id
  externalAccountId
  name
  icon
  description
  beneficiaryName
  bankAccountNumber
  routingNumber
  createdAt
  metadata {
    __typename
    id
    balance {
      cents
      formatted
      __typename
    }
  }
  limits {
    dailyCreditLimit {
      cents
      __typename
    }
    remainingDailyCreditLimit {
      cents
      formatted
      __typename
    }
    remainingMonthlyCreditLimit {
      cents
      formatted
      __typename
    }
    __typename
  }
}
fragment PodNode on Pod {
  __typename
  id
  name
  icon
  description
  beneficiaryName
  type
  createdAt
  metadata {
    __typename
    id
    balance {
      cents
      formatted
      __typename
    }
  }
  showSequenceBalance
  showManualLiabilityNotification
  showManualLiabilityFundsArrivedNotification
  linkedAccountId
  goalAmountInCents
  liabilityMetadata {
    ... on LiabilityMetadata {
      __typename
      id
      subtype
      institution {
        id
        logo
        __typename
      }
      balance {
        formatted
        __typename
      }
      lastStatementBalance {
        formatted
        __typename
      }
      nextPaymentMinimumAmount {
        formatted
        __typename
      }
    }
    ... on ErrorMetadata {
      __typename
      errorCode
    }
    __typename
  }
  limits {
    dailyCreditLimit {
      cents
      __typename
    }
    remainingDailyCreditLimit {
      cents
      formatted
      __typename
    }
    remainingMonthlyCreditLimit {
      cents
      formatted
      __typename
    }
    __typename
  }
}
fragment AccountNode on Account {
  __typename
  id
  name
  type
  providerType
  canBeSourceOfTransfer
  icon
  pendingDisconnectCode
  description
  routingNumber
  bankAccountNumber
  institutionName
  beneficiaryName
  createdAt
  capabilities
  liabilityLinkedWithPlaid
  isPendingKyc
  metadata {
    ... on PlaidMetadata {
      __typename
      id
      balance {
        cents
        formatted
        __typename
      }
      institution {
        id
        name
        logo
        __typename
      }
    }
    ... on MethodMetadata {
      __typename
      id
      balance {
        cents
        formatted
        __typename
      }
    }
    ... on ManualAccountMetadata {
      __typename
      id
    }
    __typename
  }
}
"""

POD_DRAWER_CONTENT = """
query PodDrawerContent($organizationId: ID!, $id: ID!) {
  organization(id: $organizationId) {
    id
    pod(id: $id) {
      ...PodDrawer
      transferReferences(first: 5) {
        edges {
          ...TransferReferenceEdge
          __typename
        }
        __typename
      }
      __typename
    }
    __typename
  }
}
fragment PodDrawer on Pod {
  id
  name
  icon
  beneficiaryName
  bankAccountNumber
  externalAccountId
  routingNumber
  showSequenceBalance
  goalAmountInCents
  linkedAccount {
    id
    pendingDisconnectCode
    name
    __typename
  }
  metadata {
    id
    balance {
      cents
      formatted
      __typename
    }
    __typename
  }
  liabilityMetadata {
    ... on LiabilityMetadata {
      __typename
      id
      name
      mask
      balance {
        formatted
        __typename
      }
      balanceLastUpdated
      nextPaymentMinimumAmount {
        cents
        formatted
        __typename
      }
      nextPaymentDueDate
      interestRatePercentage
      lastStatementBalance {
        formatted
        __typename
      }
      subtype
    }
    ... on ErrorMetadata {
      __typename
      errorCode
      displayMessage
    }
    __typename
  }
  __typename
}
fragment TransferReferenceEdge on TransferReferenceEdge {
  cursor
  node {
    ...TransferReferenceNode
    __typename
  }
  __typename
}
fragment TransferReferenceNode on TransferReference {
  id
  type
  status
  errorReason
  createdAt
  amount {
    cents
    formatted
    __typename
  }
  source {
    ... on Pod {
      id
      name
      icon
      __typename
    }
    ... on Port {
      id
      name
      icon
      __typename
    }
    ... on Account {
      id
      name
      icon
      __typename
    }
    __typename
  }
  destination {
    ... on Pod {
      id
      name
      icon
      __typename
    }
    ... on Port {
      id
      name
      icon
      __typename
    }
    ... on Account {
      id
      name
      icon
      __typename
    }
    __typename
  }
  __typename
}
"""

ACTIVITY_SUMMARY = """
query ActivitySummary {
  me {
    id
    offer(location: ACTIVITY_SUMMARY) {
      id
      type
      name
      userId
      status
      linkedPodId
      linkedAccountId
      linkedTransferReferenceId
      data
      location
      createdAt
      updatedAt
      __typename
    }
    settings {
      id
      showSinceYouveBeenGone
      __typename
    }
    __typename
  }
  activitySummary {
    id
    transferReferencesCount
    ruleExecutionsCount
    totalIncomingFundsInCents {
      cents
      formatted
      __typename
    }
    __typename
  }
}
"""

ACTIVITY_LOG_TRANSFERS = """
query ActivityLogV2Transfers($organizationId: ID!, $transferFilter: TransferReferenceFilter!, $after: String, $first: Int!) {
  me {
    id
    offer(location: ACTIVITY_LOG) {
      id
      type
      name
      userId
      status
      linkedPodId
      linkedAccountId
      linkedTransferReferenceId
      data
      location
      createdAt
      updatedAt
      __typename
    }
    __typename
  }
  organization(id: $organizationId) {
    id
    firstTransferDate
    kycs {
      id
      name
      kycType
      __typename
    }
    plan {
      id
      name
      transactionsPerMonth
      transferExtraCharge {
        formatted
        __typename
      }
      __typename
    }
    transferReferences(filter: $transferFilter, after: $after, first: $first) {
      pageInfo {
        endCursor
        hasNextPage
        __typename
      }
      edges {
        ...ActivityTransferReferenceEdge
        __typename
      }
      __typename
    }
    __typename
  }
}
fragment ActivityTransferReferenceEdge on TransferReferenceEdge {
  cursor
  node {
    ...ActivityTransferReferenceNode
    __typename
  }
  __typename
}
fragment ActivityTransferReferenceNode on TransferReference {
  id
  type
  status
  errorReason
  createdAt
  updatedAt
  amount {
    cents
    formatted
    __typename
  }
  source {
    ... on Pod {
      id
      name
      icon
      __typename
    }
    ... on Port {
      id
      name
      icon
      __typename
    }
    ... on Account {
      id
      name
      icon
      __typename
    }
    ... on Merchant {
      id
      name
      icon
      __typename
    }
    ... on ExternalEntity {
      name
      __typename
    }
    __typename
  }
  destination {
    ... on Pod {
      id
      name
      icon
      __typename
    }
    ... on Port {
      id
      name
      icon
      __typename
    }
    ... on Account {
      id
      name
      icon
      __typename
    }
    ... on Merchant {
      id
      name
      icon
      __typename
    }
    ... on ExternalEntity {
      name
      __typename
    }
    __typename
  }
  direction
  activityType
  description
  __typename
}
"""

TRANSFER_REFERENCE_DETAIL = """
query TransferReferenceDrawerContentV2($organizationId: ID!, $id: ID!) {
  organization(id: $organizationId) {
    id
    transferReference(id: $id) {
      id
      type
      status
      errorReason
      createdAt
      updatedAt
      amount {
        cents
        formatted
        __typename
      }
      source {
        ... on Pod {
          id
          name
          icon
          __typename
        }
        ... on Port {
          id
          name
          icon
          __typename
        }
        ... on Account {
          id
          name
          icon
          __typename
        }
        ... on Merchant {
          id
          name
          icon
          __typename
        }
        ... on ExternalEntity {
          name
          __typename
        }
        __typename
      }
      destination {
        ... on Pod {
          id
          name
          icon
          __typename
        }
        ... on Port {
          id
          name
          icon
          __typename
        }
        ... on Account {
          id
          name
          icon
          __typename
        }
        ... on Merchant {
          id
          name
          icon
          __typename
        }
        ... on ExternalEntity {
          name
          __typename
        }
        __typename
      }
      direction
      activityType
      description
      details {
        ... on SimpleTransferDetails {
          __typename
          status {
            status
            createdAt
            completedAt
            expectedCompletionDate
            __typename
          }
        }
        ... on CompoundTransferDetails {
          __typename
          pullPaymentStatus {
            status
            createdAt
            completedAt
            expectedCompletionDate
            __typename
          }
          pushPaymentStatus {
            status
            createdAt
            completedAt
            expectedCompletionDate
            __typename
          }
          reversalPaymentStatus {
            status
            createdAt
            completedAt
            expectedCompletionDate
            __typename
          }
        }
        __typename
      }
      ruleDetails {
        triggerType
        triggerCron
        __typename
      }
      __typename
    }
    __typename
  }
}
"""

"""GraphQL mutation strings for the Sequence API."""

CREATE_PAYMENT = """
mutation CreatePayment($id: ID!, $source: PaymentAccountInput!, $destination: PaymentAccountInput!, $amount: Int!, $isInstantTransfer: Boolean, $achDescription: String) {
  forKYC(id: $id) {
    createPayment(
      fields: {amount: $amount, source: $source, destination: $destination, isInstantTransfer: $isInstantTransfer, achDescription: $achDescription}
    ) {
      ok {
        organization {
          id
          pods {
            id
            name
            icon
            type
            metadata {
              id
              balance {
                cents
                formatted
                __typename
              }
              __typename
            }
            __typename
          }
          __typename
        }
        __typename
      }
      error {
        message
        __typename
      }
      __typename
    }
    __typename
  }
}
"""

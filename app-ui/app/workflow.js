'use client'

import * as React from 'react'
import axios from 'axios'
import useSWR from 'swr'

import _ from 'lodash'

export default function Workflow() {
    const { data, error, isLoading } = useSWR('/api/workflows', () => {
      return axios.get('/api/workflows').then((res) => {
        console.log(res.data)
        return res.data
        })
    })
   
    if (error) return <div>failed to load</div>
    if (isLoading) return <div>loading...</div>
  
    return (
      <div>
        <h1>Workflows</h1>
        <ul>
          {_.map(data.workflows, (workflow) => (
            <li key={workflow.id}>{workflow.name} - {workflow.id}</li>
          ))}
        </ul>
      </div>
    ) 
}
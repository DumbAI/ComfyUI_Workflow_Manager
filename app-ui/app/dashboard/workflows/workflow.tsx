'use client'

import * as React from 'react'
import axios from 'axios'
import useSWR from 'swr'

import { Button } from "@/components/ui/button"

import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import _ from 'lodash'

export default function Workflow() {
    const { data, error, isLoading } = useSWR('/api/workflows', () => {
      return axios.get('/api/workflows').then((res) => {
        console.log(res.data)
        return res.data
        })
    })

    const launchWorkflow = (workflowId: string) => {
      console.log(`Launching workflow ${workflowId}`)
      
      return axios.post(`/api/workflows/${workflowId}/run`).then((res) => {
        console.log(res.data)
        return res.data
        })
    }
   
    if (error) return <div>failed to load</div>
    if (isLoading) return <div>loading...</div>
  
    return (
      <div>
        <h1 className="text-3xl font-bold my-4">Workflows</h1>
        
        <ul>
          {_.map(data.workflows, (workflow) => (
            <li key={workflow.id}>
              <Card>
                <CardHeader>
                  <CardTitle>
                    <div className='flex flex-row justify-between'>
                      <h2>
                        {workflow.name}
                      </h2>
                      {/* TODO: all API to launch ComfyUI and return the host:port */}
                      <Button>
                        Launch
                      </Button>
                    </div>
                  </CardTitle>
                  <CardDescription>{workflow.id}</CardDescription>
                </CardHeader>
                <CardContent>
                  <p>{workflow.description}</p>
                  <p className='break-words'>{JSON.stringify(workflow)}</p>
                  <iframe src={`http://localhost:8188`} width="100%" height="800px"></iframe>
                </CardContent>
                {/* <CardFooter>
                  <p></p>
                </CardFooter> */}
              </Card>
            </li>
          ))}
        </ul>
      </div>
    ) 
}
'use client'
import { Link } from '@chakra-ui/next-js'

import * as React from 'react'
import axios from 'axios';
import useSWR from 'swr'

// 1. import `ChakraProvider` component

import {
  Drawer,
  DrawerBody,
  DrawerFooter,
  DrawerHeader,
  DrawerOverlay,
  DrawerContent,
  DrawerCloseButton,
  RadioGroup,
  Radio,
  Stack,
  Button,
  useDisclosure
} from '@chakra-ui/react'


import Image from "next/image";
import Workflow from '@/app/dashboard/workflows/workflow';



export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-between p-24">
      <div className='w-full h-screen'>
        <Workflow></Workflow>
        {/* <iframe className='w-full h-screen' src='http://127.0.0.1:8188' allowFullScreen/>  */}
        {/* <iframe className='w-full h-screen' src='http://localhost:8188' allowFullScreen/>  */}
      </div>
    </main>
  );
}

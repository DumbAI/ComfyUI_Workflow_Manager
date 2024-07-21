'use client'
import { Link } from '@chakra-ui/next-js'

import * as React from 'react'
import axios from 'axios';
import useSWR from 'swr'

// 1. import `ChakraProvider` component
import { ChakraProvider } from '@chakra-ui/react'

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
import Workflow from './workflow';

function Sidebar() {
  const { isOpen, onOpen, onClose } = useDisclosure()
  const [placement, setPlacement] = React.useState('left')



  return (
    <>
      <Button colorScheme='blue' onClick={onOpen}>
        Open
      </Button>
      <Drawer placement={'left'} onClose={onClose} isOpen={isOpen}>
        <DrawerOverlay />
        <DrawerContent>
          <DrawerHeader borderBottomWidth='1px'>Basic Drawer</DrawerHeader>
          <DrawerBody>
            <p>Some contents...</p>
            <p>Some contents...</p>
            <p>Some contents...</p>
            <div className="z-10 w-full max-w-5xl items-center justify-between font-mono text-sm lg:flex">
            <p className="fixed left-0 top-0 flex w-full justify-center border-b border-gray-300 bg-gradient-to-b from-zinc-200 pb-6 pt-8 backdrop-blur-2xl dark:border-neutral-800 dark:bg-zinc-800/30 dark:from-inherit lg:static lg:w-auto  lg:rounded-xl lg:border lg:bg-gray-200 lg:p-4 lg:dark:bg-zinc-800/30">
              Get started by editing&nbsp;
              <Link href='/api/workflows' color='blue.400' _hover={{ color: 'blue.500' }}>
              api/index.py
              </Link>
              {/* <Link href="/api/python">
                <code className="font-mono font-bold">api/index.py</code>
              </Link> */}
            </p>
          </div>
          </DrawerBody>
        </DrawerContent>
      </Drawer>
    </>
  )
}



export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-between p-24">
      <Sidebar></Sidebar> 
      
      <div className='w-full h-screen'>
        <Workflow></Workflow>
        {/* <iframe className='w-full h-screen' src='http://127.0.0.1:8188' allowFullScreen/>  */}
        {/* <iframe className='w-full h-screen' src='http://localhost:8188' allowFullScreen/>  */}
      </div>
    </main>
  );
}

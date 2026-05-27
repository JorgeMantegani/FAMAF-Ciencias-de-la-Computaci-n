simple Generator
{
    parameters:
        volatile double generationInterval; // sec
        int packetByteSize;                 // bytes
        @display("i=block/source");
    gates:
        output out;
}

simple Queue
{
    parameters:
        volatile double serviceTime; // sec
        int bufferSize;
        int ecnThreshold = default(0); // 0 = usar 0.8
        @display("i=block/queue;q=buffer");
    gates:
        input in;
        output out;
}

simple Sink
{
    parameters:
        @display("i=block/sink");
    gates:
        input in;
}

simple TransportTx
{
    parameters:
        int bufferSize;
        double initialCwnd = default(1);
        int initialRwnd = default(200);
        @display("i=block/star");
    gates:
        input toApp;
        inout toOut;
}

simple TransportRx
{
    parameters:
        int bufferSize;
        @display("i=block/star");
    gates:
        output toApp;
        inout toOut;
}

module NodeTx
{
    gates:
        inout out;
    submodules:
    gen: Generator {
        @display("p=70,50");
    }
    transport : TransportTx;
    connections:
        gen.out --> transport.toApp;
        transport.toOut <--> out;
}

module NodeRx
{
    parameters:
      double rxToSinkDatarate @unit(bps) = default(1Mbps);
    gates:
        inout in;
    submodules:
        transport: TransportRx;
        sink: Sink {
            @display("p=70,140");
        }
    connections:
        in <--> transport.toOut;
        transport.toApp --> { datarate = parent.rxToSinkDatarate; } --> sink.in;
}


network Network
{
    parameters:
        double txToQueueDatarate @unit(bps) = default(1Mbps);
        double queueToRxDatarate @unit(bps) = default(1Mbps);
        double feedbackDatarate @unit(bps) = default(1Mbps);
        double linkDelay @unit(s) = default(100us);
    
    @display("bgl=2");

    submodules:
        nodeTx: NodeTx{
            @display("p=50,100");
        }
        queue: Queue{
            @display("p=200,100");
        }
        feedbackQueue: Queue{
            @display("p=200,200");
        }
        nodeRx: NodeRx{
            @display("p=350,100");
        }
    
    connections:
        nodeTx.out$o --> {
            datarate = parent.txToQueueDatarate;
            delay = parent.linkDelay;
        } --> queue.in;

        queue.out --> {
            datarate = parent.queueToRxDatarate;
            delay = parent.linkDelay;
        } --> nodeRx.in$i;

        nodeRx.in$o --> {
            datarate = parent.feedbackDatarate;
            delay = parent.linkDelay;
        } --> feedbackQueue.in;

        feedbackQueue.out --> {
            datarate = parent.feedbackDatarate;
            delay = parent.linkDelay;
        } --> nodeTx.out$i;
}

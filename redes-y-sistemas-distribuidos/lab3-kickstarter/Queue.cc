#ifndef QUEUE
#define QUEUE

#include <string.h>
#include <omnetpp.h>

using namespace omnetpp;

enum PacketKind {
    DATA = 1,
    ACK = 2,
    WINDOW_UPDATE = 3
};

class Queue: public cSimpleModule {
private:
    cQueue buffer;
    cMessage *endServiceEvent;
    int bufferSize;
    long droppedPackets;
    cOutVector bufferSizeVector;
    cOutVector droppedPacketsVector;
    simtime_t serviceTime;

    // debug
    int totalPackets;
    cOutVector totalPacketsVector;

    int ecnThreshold;
    long markedPackets;
    cOutVector markedPacketsVector;
public:
    Queue();
    virtual ~Queue();
protected:
    virtual void initialize();
    virtual void finish();
    virtual void handleMessage(cMessage *msg);
};

Define_Module(Queue);

Queue::Queue() {
    endServiceEvent = NULL;
}

Queue::~Queue() {
    cancelAndDelete(endServiceEvent);
}

void Queue::initialize() {
    buffer.setName("buffer");
    endServiceEvent = new cMessage("endService");

    bufferSize = par("bufferSize");
    droppedPackets = 0;
    markedPackets = 0;

    //debug
    totalPackets = 0;
    totalPacketsVector.setName("totalPackets");

    ecnThreshold = par("ecnThreshold");
    if (ecnThreshold == 0) {
        ecnThreshold = (int)(bufferSize * 0.8); //arbitrario
    }

    bufferSizeVector.setName("bufferSize");
    droppedPacketsVector.setName("droppedPackets");
    markedPacketsVector.setName("markedPackets");
}

void Queue::finish() {
    recordScalar("Dropped packets", droppedPackets);
    recordScalar("Marked packets (ECN)", markedPackets);
    recordScalar("Total received packets", totalPackets);
}

void Queue::handleMessage(cMessage *msg) {
    //debug
    totalPackets++;
    totalPacketsVector.record(totalPackets);
    // if msg is signaling an endServiceEvent
    if (msg == endServiceEvent) {
        // if packet in buffer, send next one
        if (!buffer.isEmpty()) {
            // dequeue packet
            cPacket *pkt = check_and_cast<cPacket *>(buffer.pop());

            cChannel *channel = gate("out")->findTransmissionChannel();
            simtime_t serviceTime = channel ? channel->calculateDuration(pkt) : SIMTIME_ZERO;

            bufferSizeVector.record(buffer.getLength());
            // send packet
            send(pkt, "out");
            // start new service
            scheduleAt(simTime() + serviceTime, endServiceEvent);
        }
    } else {
        cPacket *pkt = check_and_cast<cPacket *>(msg);
        int currentLength = buffer.getLength();

        //si el buffer supera el umbral marcamos paquete
        if (currentLength >= ecnThreshold) {
            if(!pkt->hasPar("ecn")){
                pkt->addPar("ecn");
            }
            pkt->par("ecn") = true;
            markedPackets++;
            markedPacketsVector.record(markedPackets);
            EV << "Packets marked with ECN, buffer occupancy: " << currentLength << "/" << bufferSize << "\n";
        }

        //encolado del paquete
        if (buffer.getLength() < bufferSize) {
            buffer.insert(pkt);
            bufferSizeVector.record(buffer.getLength());
        } else {    //buffer lleno, descartamos
            droppedPackets ++;
            droppedPacketsVector.record(droppedPackets);
            delete pkt;
            return;
        }

        if(!endServiceEvent->isScheduled()){
            scheduleAt(simTime(), endServiceEvent);
        }
    }
}

#endif /* QUEUE */

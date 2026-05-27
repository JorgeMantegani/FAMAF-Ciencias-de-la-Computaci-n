#ifndef TRANSPORTTX
#define TRANSPORTTX

#include <queue>
#include <omnetpp.h>

using namespace omnetpp;

enum PacketKind {
    DATA = 1,
    ACK = 2,
    WINDOW_UPDATE = 3
};

class TransportTx : public cSimpleModule {
    private:
        std::queue<cPacket*> txBuffer;
        cMessage *sendEvent;

        // variables de ventana
        double cwnd;
        int rwnd;
        int inFlight;
        int bufferSize;

        //estadisticas
        cOutVector cwndVector;
        cOutVector rwndVector;
        cOutVector effectiveWindowVector;
        cOutVector inFlightVector;
        cOutVector txQueueOccupancyVector;

        long totalPacketsSent;
        long totalPacketsAcked;
        long congestionEvents;
    public:
        TransportTx() : sendEvent(nullptr) {}
        virtual ~TransportTx() {
            cancelAndDelete(sendEvent);
            while (!txBuffer.empty()) {
                delete txBuffer.front();
                txBuffer.pop();
            }
        }
    protected:
    virtual void initialize() override {
        cwnd = par("initialCwnd");
        rwnd = par("initialRwnd");
        bufferSize = par("bufferSize");
        inFlight = 0;
        totalPacketsSent = 0;
        totalPacketsAcked = 0;
        congestionEvents = 0;

        sendEvent = new cMessage("sendEvent");

        cwndVector.setName("cwnd");
        rwndVector.setName("rwnd");
        effectiveWindowVector.setName("effectiveWindow");
        inFlightVector.setName("inFlight");
        txQueueOccupancyVector.setName("txQueueOccupancy");

        EV << "TransportTx initialized: cwnd=" << cwnd << ", rwnd=" << rwnd << "\n";
    }

    virtual void handleMessage(cMessage *msg) override {
        if (msg == sendEvent) {
            sendPacket();
        }else if(!msg->isSelfMessage()){
            if (msg->getKind() == ACK) {
                cPacket *ack = check_and_cast<cPacket*>(msg);
                handleAck(ack, false);
            }
            else if (msg->getKind() == WINDOW_UPDATE){
                cPacket *update = check_and_cast<cPacket*>(msg);
                handleAck(update, true);
            }else{
                cPacket *pkt = check_and_cast<cPacket*>(msg);
                enqueuePacket(pkt);
            }
        }else{
            delete msg;
        }
    }

    void enqueuePacket(cPacket *pkt) {
        if((int)txBuffer.size() >= bufferSize) {
            EV << "TX buffer full, dropping packet\n";
            delete pkt;
            return;
        }

        txBuffer.push(pkt);
        txQueueOccupancyVector.record(txBuffer.size());

        if(!sendEvent->isScheduled()) {
            scheduleAt(simTime(), sendEvent);
        }
    }

    bool canSend() {
        int effectiveWindow = std::min((int)cwnd, rwnd);
        effectiveWindowVector.record(effectiveWindow);
        return (inFlight < effectiveWindow) && !txBuffer.empty();
    }

    void sendPacket(){
        if (!canSend()) {
            return;
        }

        cChannel *channel = gate("toOut$o")->findTransmissionChannel();
        if (channel && channel->isBusy()) {
            if (!sendEvent->isScheduled()){
                scheduleAt(channel->getTransmissionFinishTime(), sendEvent);
            }
            return;
        }

        cPacket *pkt = txBuffer.front();
        txBuffer.pop();

        
        pkt->setKind(DATA);

        inFlight++;
        totalPacketsSent++;

        send(pkt, "toOut$o");

        cwndVector.record(cwnd);
        rwndVector.record(rwnd);
        inFlightVector.record(inFlight);
        txQueueOccupancyVector.record(txBuffer.size());

        if (canSend() && !txBuffer.empty()) {
            simtime_t serviceTime = channel ? channel->calculateDuration(pkt) : SIMTIME_ZERO;
            if(!sendEvent->isScheduled()) {
                scheduleAt(simTime() + serviceTime, sendEvent);
            }
        }
    }

    void handleAck(cPacket *ack, bool isWindowUpdate) {
        // actualizar rwnd desde el ack
        if (ack->hasPar("rwnd")) {
            rwnd = ack->par("rwnd").longValue();
        }

        // verificar congestion
        bool congestion = false;
        if (ack->hasPar("ecn")){
            congestion = ack->par("ecn").boolValue();
        }

        if(!isWindowUpdate && inFlight > 0) {
            inFlight--;
            totalPacketsAcked++;
        }

        // AIMD: Additive Increase Multiplicative Decrease
        if (congestion) {
            // Multiplicative Decrease: reducimos cwnd a la mitad
            double oldCwnd = cwnd;
            cwnd = std::max(1.0, cwnd / 2.0);
            congestionEvents++;
            EV << "CONGESTION! cwnd: " << oldCwnd << " -> " << cwnd << "\n";
        }else if (ack->getKind() == ACK) {
            //Additive Increase: aumentamos cwnd
            inFlight = std::max(0, inFlight -1);
            totalPacketsAcked++;
            cwnd += 1.0 / cwnd;
        }

        delete ack;

        if(!sendEvent->isScheduled() && canSend()) {
            scheduleAt(simTime(), sendEvent);
        }
    }

    virtual void finish() override {
        recordScalar("Total packets sent", totalPacketsSent);
        recordScalar("Total packets acked", totalPacketsAcked);
        recordScalar("Congestion events", congestionEvents);
        recordScalar("Final cwnd", cwnd);
        recordScalar("Final rwnd", rwnd);
    }
};

Define_Module(TransportTx);
#endif
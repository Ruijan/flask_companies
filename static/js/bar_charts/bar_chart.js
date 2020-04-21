class BarChart{
    constructor(container_name, data) {
        this.root = this.transformData(data)
        this.c_name = container_name
        this.margin = ({top: 30, right: 30, bottom: 0, left: 200})
        this.barStep = 27
        this.barPadding = 3 / this.barStep
        this.container = d3.select(container_name)
        this.width = this.container.node().getBoundingClientRect().width - this.margin.right;
        this.height = this.getHeight()
        this.container.style("height", (this.height + this.margin.bottom + this.margin.top)+"px");
    }

    getHeight(){
        return 0;
    }

    transformData(data){
        return data
    }
}